# -*- coding: utf-8 -*-
"""
QA Hardening and Duplication Test Suite for ClipMind
Tests timeline overlaps, semantic duplication (Jaccard), fallback safety, short/long videos, and concurrent job caching.
"""

import sys
import os
import json
import time
import asyncio
from unittest.mock import patch, MagicMock

# Adjust sys.path to import modules from backend
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analyzer import analyze_with_gemini, _validate_clips, _deduplicate_candidates
from main import app, url_to_job_id, cache_lock

# Color helpers for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

class MockTranscriptEntry:
    def __init__(self, start, duration, text=""):
        self.start = float(start)
        self.duration = float(duration)
        self.text = text

# Helper to print test results
results = []
PASS = "PASS"
FAIL = "FAIL"

def record(test_name, status, detail=""):
    results.append((test_name, status, detail))
    status_str = f"{GREEN}[OK] PASS{RESET}" if status == PASS else f"{RED}[!!] FAIL{RESET}"
    print(f"  {status_str}: {test_name}")
    if detail:
        print(f"        {detail}")

def check_overlaps(clips):
    """Returns True if any two clips overlap temporally."""
    n = len(clips)
    for i in range(n):
        for j in range(i + 1, n):
            c1, c2 = clips[i], clips[j]
            if max(c1["start_time"], c2["start_time"]) < min(c1["end_time"], c2["end_time"]):
                return True
    return False

def check_jaccard_violations(clips, threshold=0.6):
    """Returns True if any two clips share Jaccard similarity > threshold."""
    n = len(clips)
    for i in range(n):
        for j in range(i + 1, n):
            c1, c2 = clips[i], clips[j]
            set1 = set(range(c1["start_index"], c1["end_index"] + 1))
            set2 = set(range(c2["start_index"], c2["end_index"] + 1))
            intersection = len(set1.intersection(set2))
            union = len(set1.union(set2))
            jaccard = intersection / union if union > 0 else 0.0
            if jaccard > threshold:
                return True
    return False

# ──────────────────────────────────────────────────────────────
# TEST RUNNERS
# ──────────────────────────────────────────────────────────────

def run_tests():
    print("=" * 70)
    print("  QA HARDENING & DEDUPLICATION TEST SUITE")
    print("=" * 70)

    # --- Test Case 1: Curator Fallback Safety ---
    # When curator fails, Scout candidates must be deduplicated
    try:
        dummy_transcript = [MockTranscriptEntry(float(i * 5), 5.0, f"Line {i}") for i in range(40)]
        scout_candidates = [
            {"title": "Candidate A", "start_index": 2, "end_index": 8, "virality_score": 9.0},
            {"title": "Candidate B", "start_index": 3, "end_index": 9, "virality_score": 8.0},  # Overlaps A
            {"title": "Candidate C", "start_index": 15, "end_index": 22, "virality_score": 9.5},
            {"title": "Candidate D", "start_index": 16, "end_index": 23, "virality_score": 7.0}, # Overlaps C
            {"title": "Candidate E", "start_index": 30, "end_index": 35, "virality_score": 8.5}
        ]

        def mock_llm_call_fallback(system_prompt, user_prompt, response_json=True, **kwargs):
            if "short-form video researcher" in system_prompt:
                return json.dumps({"candidates": scout_candidates})
            elif "content curator assistant" in system_prompt:
                raise RuntimeError("Simulated Curator Error")
            elif "dialogue editor" in system_prompt:
                import re
                m_start = re.search(r"Current Start Index:\s*(\d+)", user_prompt)
                m_end = re.search(r"Current End Index:\s*(\d+)", user_prompt)
                return json.dumps({
                    "adjusted_start_index": int(m_start.group(1)) if m_start else 0,
                    "adjusted_end_index": int(m_end.group(1)) if m_end else 10,
                    "explanation": "Refined"
                })
            elif "digital marketing assistant" in system_prompt:
                return json.dumps({"shorts_title": "SEO", "shorts_description": "SEO", "shorts_tags": []})
            return "{}"

        with patch("analyzer.LLMResilienceManager") as MockResilience:
            inst = MagicMock()
            inst.primary_key = "real_api_key_test"
            inst.call.side_effect = mock_llm_call_fallback
            MockResilience.return_value = inst

            # Execute pipeline
            res = analyze_with_gemini(
                transcript="This is a valid long transcript for testing purposes.",
                raw_transcript=dummy_transcript,
                api_key="real_api_key_test",
                num_clips=5
            )

            # Check overlap and count
            has_overlap = check_overlaps(res)
            has_jaccard = check_jaccard_violations(res)
            
            if not has_overlap and not has_jaccard:
                record("Curator Fallback Safety: candidate list deduplicated programmatically", PASS)
            else:
                record("Curator Fallback Safety: candidate list deduplicated programmatically", FAIL,
                       f"Overlaps detected: {has_overlap}, Jaccard violation: {has_jaccard}")
    except Exception as e:
        record("Curator Fallback Safety: candidate list deduplicated programmatically", FAIL, f"Exception: {e}")

    # --- Test Case 2: Repetitive Speech & Semantic Redundancy ---
    # Prune candidates that cover identical transcript lines (Jaccard > 60%)
    try:
        # Candidate 1: [10 - 20], Candidate 2: [11 - 19] -> Jaccard similarity is 9/11 = 81.8%
        raw_items = [MockTranscriptEntry(float(i*5), 5.0) for i in range(30)]
        clips_to_validate = [
            {"title": "Original Clip", "start_index": 10, "end_index": 20, "virality_score": 9.0},
            {"title": "Redundant Clip", "start_index": 11, "end_index": 19, "virality_score": 8.0}
        ]
        
        validated = _validate_clips(clips_to_validate, raw_items)
        if len(validated) == 1 and validated[0]["title"] == "Original Clip":
            record("Semantic Redundancy: prunes high-overlap Jaccard candidate (>60%)", PASS)
        else:
            record("Semantic Redundancy: prunes high-overlap Jaccard candidate (>60%)", FAIL,
                   f"Expected 1 clip (Original Clip), got {len(validated)}: {[c['title'] for c in validated]}")
    except Exception as e:
        record("Semantic Redundancy: prunes high-overlap Jaccard candidate (>60%)", FAIL, f"Exception: {e}")

    # --- Test Case 3: Short Video Safety ---
    # Under a 30s video, request 5 clips. Deduplication must clamp output to 1 clip without crashing.
    try:
        # 30-second transcript
        short_transcript = [MockTranscriptEntry(float(i*5), 5.0) for i in range(6)]
        scout_cand = [
            {"title": "Clip A", "start_index": 0, "end_index": 5, "virality_score": 9.0},
            {"title": "Clip B", "start_index": 1, "end_index": 5, "virality_score": 8.0},
            {"title": "Clip C", "start_index": 0, "end_index": 4, "virality_score": 7.0}
        ]
        
        # All candidates overlap. Programmatic deduplication should return exactly 1 clip (highest score = Clip A)
        with patch("analyzer.LLMResilienceManager") as MockResilience:
            inst = MagicMock()
            inst.primary_key = "real_key"
            def mock_call(system_prompt, user_prompt, **kwargs):
                if "researcher" in system_prompt:
                    return json.dumps({"candidates": scout_cand})
                elif "scoring" in system_prompt:
                    if "Clip A" in user_prompt:
                        return json.dumps({"hook_strength": 9, "first_3_second_hook": 9, "curiosity_gap": 9, "emotional_intensity": 9, "controversy": 5, "surprise": 5, "actionability": 5, "storytelling": 5, "reasoning": {}})
                    elif "Clip B" in user_prompt:
                        return json.dumps({"hook_strength": 4, "first_3_second_hook": 4, "curiosity_gap": 4, "emotional_intensity": 4, "controversy": 4, "surprise": 4, "actionability": 4, "storytelling": 4, "reasoning": {}})
                    else:
                        return json.dumps({"hook_strength": 3, "first_3_second_hook": 3, "curiosity_gap": 3, "emotional_intensity": 3, "controversy": 3, "surprise": 3, "actionability": 3, "storytelling": 3, "reasoning": {}})
                return "{}"
            inst.call.side_effect = mock_call
            MockResilience.return_value = inst
            
            res = analyze_with_gemini(
                transcript="This is a valid long transcript for testing purposes.",
                raw_transcript=short_transcript,
                api_key="real_key",
                num_clips=5
            )
            
            if len(res) == 1 and res[0]["title"] == "Clip A":
                record("Short Video: returns maximum possible unique clips (1) instead of overlapping sets", PASS)
            else:
                record("Short Video: returns maximum possible unique clips (1)", FAIL, f"Got {len(res)}: {[c['title'] for c in res]}")
    except Exception as e:
        record("Short Video: returns maximum possible unique clips (1)", FAIL, f"Exception: {e}")

    # --- Test Case 4: Long Video Overlap Sweep ---
    # Simulated 1-hour video (720 lines). Prunes many overlapping segments.
    try:
        long_transcript = [MockTranscriptEntry(float(i*5), 5.0) for i in range(720)]
        long_candidates = []
        for i in range(20):
            # Create systematic overlaps
            long_candidates.append({
                "title": f"Candidate {i}",
                "start_index": i * 10,
                "end_index": i * 10 + 6, # overlaps slightly with i*10 + 5
                "virality_score": float(10 - i * 0.1)
            })
            # Duplicate covering same range
            long_candidates.append({
                "title": f"Duplicate {i}",
                "start_index": i * 10 + 1,
                "end_index": i * 10 + 5,
                "virality_score": float(5.0)
            })
            
        validated = _validate_clips(long_candidates, long_transcript)
        has_overlap = check_overlaps(validated)
        has_jaccard = check_jaccard_violations(validated)
        
        if not has_overlap and not has_jaccard:
            record("Long Video: programmatically prunes multi-overlap pools on large transcripts", PASS, f"Extracted {len(validated)} clean non-overlapping clips.")
        else:
            record("Long Video: programmatically prunes multi-overlap pools on large transcripts", FAIL, f"Overlap: {has_overlap}, Jaccard: {has_jaccard}")
    except Exception as e:
        record("Long Video: programmatically prunes multi-overlap pools on large transcripts", FAIL, f"Exception: {e}")

    # --- Test Case 5: Job Cache & URL Normalization Reuse ---
    # Concurrent/duplicate URL submissions (with different formats) must return the same job ID
    try:
        import asyncio
        from main import analyze_video, AnalyzeRequest
        
        # Setup mock requests in different formats for the same VIDEOID (dQw4w9WgXcQ)
        reqs = [
            AnalyzeRequest(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ", gemini_api_key="real_key_abc"),
            AnalyzeRequest(url="https://youtu.be/dQw4w9WgXcQ", gemini_api_key="real_key_abc"),
            AnalyzeRequest(url="https://youtube.com/watch?v=dQw4w9WgXcQ&t=100", gemini_api_key="real_key_abc"),
            AnalyzeRequest(url="https://youtube.com/shorts/dQw4w9WgXcQ", gemini_api_key="real_key_abc")
        ]
        
        # Clear cache first
        url_to_job_id.clear()
        
        class DummyBackgroundTask:
            def add_task(self, func, *args, **kwargs):
                pass
        
        # Force check_ffmpeg to return True
        with patch("main.check_ffmpeg", return_value=True):
            # Run concurrently
            async def run_reqs():
                bg = DummyBackgroundTask()
                results_list = []
                for r in reqs:
                    results_list.append(await analyze_video(r, bg))
                return results_list
                
            res_list = asyncio.run(run_reqs())
            
            job_ids = [r["job_id"] for r in res_list]
            if len(set(job_ids)) == 1:
                record("Job Cache: duplicate URL submissions reuse active job ID", PASS, f"Reused job ID {job_ids[0]} across all 4 different YouTube URL formats.")
            else:
                record("Job Cache: duplicate URL submissions reuse active job ID", FAIL, f"URL formats returned different job IDs: {job_ids}")
    except Exception as e:
        record("Job Cache: duplicate URL submissions reuse active job ID", FAIL, f"Exception: {e}")

    # ──────────────────────────────────────────────────────────────
    # SUMMARY
    # ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  QA HARDENING SUMMARY")
    print("=" * 60)
    passed = [r for r in results if r[1] == PASS]
    failed = [r for r in results if r[1] == FAIL]
    print(f"  Total Tests: {len(results)}")
    print(f"  PASSED: {len(passed)}")
    print(f"  FAILED: {len(failed)}")
    print("=" * 60)
    
    sys.exit(0 if not failed else 1)

if __name__ == "__main__":
    run_tests()
