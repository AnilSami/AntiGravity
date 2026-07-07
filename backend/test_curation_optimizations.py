"""
test_curation_optimizations.py — Hardening & Edge Case tests for Phase 24 optimizations
"""

import os
import sys
import unittest
import time
from unittest.mock import patch, MagicMock

# Ensure backend is on path
sys.path.insert(0, os.path.dirname(__file__))

from analyzer import analyze_with_gemini
from job_manager import JobStatus
from main import jobs, url_to_job_id, cleanup_old_jobs

class SynchronousExecutor:
    def __init__(self, *args, **kwargs):
        pass
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def submit(self, fn, *args, **kwargs):
        future = MagicMock()
        try:
            res = fn(*args, **kwargs)
            future.result.return_value = res
        except Exception as e:
            future.result.side_effect = e
        return future

def mock_as_completed(futures):
    # If futures is a dict, return its keys, else return list
    if isinstance(futures, dict):
        return list(futures.keys())
    return list(futures)

@patch("analyzer.ThreadPoolExecutor", SynchronousExecutor)
@patch("analyzer.as_completed", mock_as_completed)
class TestCurationOptimizations(unittest.TestCase):
    def test_zero_candidates(self):
        """If Clip Scout returns 0 candidates, analyze_with_gemini returns empty list without crashing."""
        with patch("analyzer.LLMResilienceManager") as mock_llm_class:
            mock_llm = MagicMock()
            mock_llm_class.return_value = mock_llm
            # Scout returns empty candidates dict
            mock_llm.call.return_value = '{"candidates": []}'

            res = analyze_with_gemini(
                transcript="This is a very long transcript designed to pass the verbal check of ten characters.",
                raw_transcript=[MagicMock(text="line 1", start=0.0, duration=1.0)],
                api_key="real-api-key",
                num_clips=3
            )
            self.assertEqual(res, [])

    def test_one_candidate(self):
        """If Clip Scout returns 1 candidate, it is processed and returned successfully."""
        with patch("analyzer.LLMResilienceManager") as mock_llm_class:
            mock_llm = MagicMock()
            mock_llm.primary_key = "real-api-key"
            mock_llm_class.return_value = mock_llm
            # Scout returns 1 candidate, Curator selects 1, Editor/Publisher keeps it, post-scoring gives score
            mock_llm.call.side_effect = [
                '{"candidates": [{"title": "Only One", "start_index": 0, "end_index": 0, "reason": "Engaging"}]}', # Scout
                '{"score": 8.5, "reasoning": "Excellent"}', # Scoring
                '{"selected_clips": [{"title": "Only One", "start_index": 0, "end_index": 0, "reason": "Engaging"}]}', # Curator
                '{"adjusted_start_index": 0, "adjusted_end_index": 0, "explanation": "Clean"}', # Editor
                '{"shorts_title": "Only One Title", "shorts_description": "Desc", "shorts_tags": []}', # Publisher
                '{"score": 8.5, "reasoning": "Excellent"}' # Post-Scoring
            ]

            raw_transcript = [MagicMock(text="line 1", start=0.0, duration=5.0)]
            res = analyze_with_gemini(
                transcript="This is a very long transcript designed to pass the verbal check of ten characters.",
                raw_transcript=raw_transcript,
                api_key="real-api-key",
                num_clips=1
            )
            self.assertEqual(len(res), 1)
            self.assertEqual(res[0]["title"], "Only One")

    def test_many_candidates_sampling_100(self):
        """Verify 100 candidates are sampled down to max(5, num_clips * 2) before calling Scoring Agent."""
        with patch("analyzer.LLMResilienceManager") as mock_llm_class:
            mock_llm = MagicMock()
            mock_llm.primary_key = "real-api-key"
            mock_llm_class.return_value = mock_llm
            
            # Clip Scout returns 100 candidates
            candidates = [{"title": f"Cand {i}", "start_index": 0, "end_index": 0, "reason": "viral"} for i in range(100)]
            
            # Setup mock side effect for:
            # 1. Scout call
            # 2. Scoring Agent calls (should be exactly 6 calls if num_clips = 3, max(5, 3*2) = 6)
            # 3. Curator call
            # 4. Editor, Publisher, Post-Scoring calls for the curated clips
            import json
            mock_scout_response = json.dumps({"candidates": candidates})
            mock_curator_response = '{"selected_clips": [{"title": "Cand 0", "start_index": 0, "end_index": 0, "reason": "viral"}]}'
            
            side_effects = [mock_scout_response]
            # 6 calls to Scoring Agent (each returns a score dict)
            for _ in range(6):
                side_effects.append('{"score": 9.0, "reasoning": "good"}')
            # 1 call to Curator
            side_effects.append(mock_curator_response)
            # 1 call to Editor
            side_effects.append('{"adjusted_start_index": 0, "adjusted_end_index": 0, "explanation": "Clean"}')
            # 1 call to Publisher
            side_effects.append('{"shorts_title": "Final title", "shorts_description": "desc", "shorts_tags": []}')
            # 1 call to post evaluation
            side_effects.append('{"score": 9.2, "reasoning": "viral"}')
            
            mock_llm.call.side_effect = side_effects

            raw_transcript = [MagicMock(text="line 1", start=0.0, duration=5.0)]
            res = analyze_with_gemini(
                transcript="This is a very long transcript designed to pass the verbal check of ten characters.",
                raw_transcript=raw_transcript,
                api_key="real-api-key",
                num_clips=3
            )
            
            # Total call count check
            # Scout (1) + Scoring (6) + Curator (1) + Editor (1) + Publisher (1) = 10 calls
            self.assertEqual(mock_llm.call.call_count, 10)
            # Verify it capped list to requested num_clips
            self.assertEqual(len(res), 1)

    def test_num_clips_capping(self):
        """Verify final clips list is capped strictly to num_clips even if curator selects more."""
        with patch("analyzer.LLMResilienceManager") as mock_llm_class:
            mock_llm = MagicMock()
            mock_llm.primary_key = "real-api-key"
            mock_llm_class.return_value = mock_llm
            
            # Scout returns 2 candidates, Capping requested is 1
            mock_llm.call.side_effect = [
                '{"candidates": [{"title": "A", "start_index": 0, "end_index": 0, "reason": "x"}, {"title": "B", "start_index": 0, "end_index": 0, "reason": "x"}]}', # Scout
                '{"score": 7.0, "reasoning": "x"}', # Scoring A
                '{"score": 8.0, "reasoning": "x"}', # Scoring B
                '{"selected_clips": [{"title": "A", "start_index": 0, "end_index": 0, "reason": "x"}, {"title": "B", "start_index": 0, "end_index": 0, "reason": "x"}]}', # Curator selects both
                '{"adjusted_start_index": 0, "adjusted_end_index": 0, "explanation": "Clean"}', # Editor A
                '{"shorts_title": "Title A", "shorts_description": "desc", "shorts_tags": []}' # Publisher A
            ]

            raw_transcript = [MagicMock(text="line 1", start=0.0, duration=5.0)]
            res = analyze_with_gemini(
                transcript="This is a very long transcript designed to pass the verbal check of ten characters.",
                raw_transcript=raw_transcript,
                api_key="real-api-key",
                num_clips=1
            )
            # Capped strictly to 1 clip
            self.assertEqual(len(res), 1)
            # Scout (1) + Scoring (2) + Curator (1) + Editor (1) + Publisher (1) = 6 calls
            self.assertEqual(mock_llm.call.call_count, 6)

    def test_cleanup_old_jobs_rules(self):
        """Verify cleanup_old_jobs only purges completed/failed jobs older than 1h, and active jobs only older than 3h."""
        jobs.clear()
        url_to_job_id.clear()

        # Job 1: Completed, 30 mins old -> Should NOT be purged
        jobs["job-1"] = JobStatus(
            id="job-1", status="completed", progress=100, message="done", created_at=time.time() - 1800
        )
        # Job 2: Completed, 70 mins old -> Should be purged
        jobs["job-2"] = JobStatus(
            id="job-2", status="completed", progress=100, message="done", created_at=time.time() - 4200
        )
        # Job 3: Active (clipping), 70 mins old -> Should NOT be purged (still processing!)
        jobs["job-3"] = JobStatus(
            id="job-3", status="clipping", progress=50, message="rendering", created_at=time.time() - 4200
        )
        # Job 4: Active (clipping), 4 hours old -> Should be purged (assumed hung)
        jobs["job-4"] = JobStatus(
            id="job-4", status="clipping", progress=50, message="rendering", created_at=time.time() - 15000
        )

        with patch("asyncio.sleep", side_effect=[None, Exception("break-loop")]):
            try:
                import asyncio
                asyncio.run(cleanup_old_jobs())
            except Exception as e:
                if str(e) != "break-loop":
                    raise e

        self.assertIn("job-1", jobs)
        self.assertNotIn("job-2", jobs)
        self.assertIn("job-3", jobs)
        self.assertNotIn("job-4", jobs)

if __name__ == "__main__":
    unittest.main()
