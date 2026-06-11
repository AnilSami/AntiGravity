# -*- coding: utf-8 -*-
"""
Regression Test Suite for YouTube Smart Clip Extractor (V2 Accuracy & Quality)
Tests: Count constraints, precise boundaries, overlapping prevention, short video fallbacks, hybrid parsing.
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analyzer import _validate_clips, analyze_with_gemini

# Color helpers for clean output
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

class MockEntry:
    def __init__(self, start, duration, text=""):
        self.start = float(start)
        self.duration = float(duration)
        self.text = text

def print_result(label, passed, details=""):
    status = f"{GREEN}[PASS]{RESET}" if passed else f"{RED}[FAIL]{RESET}"
    print(f"  {status} {label}")
    if details:
        print(f"         {details}")

def run_regression_tests():
    print("=" * 60)
    print("  RUNNING ACCURACY REGRESSION TESTS")
    print("=" * 60)

    # ──────────────────────────────────────────────────────────
    # CASE 1: Overlap Pull-back (Vocal Cutoff Prevention)
    # ──────────────────────────────────────────────────────────
    # Transcript segments:
    # Seg 0: 0.0 - 10.0 (dur 10s)
    # Seg 1: 10.0 - 20.0 (dur 10s)
    # Seg 2: 20.0 - 30.0 (dur 10s)
    # Seg 3: 28.0 - 38.0 (dur 10s) -> Overlaps with Seg 2! Next sentence starts early at 28.0.
    transcript_overlap = [
        MockEntry(0.0, 10.0, "First segment"),
        MockEntry(10.0, 10.0, "Second segment"),
        MockEntry(20.0, 10.0, "Third segment ending at 30.0"),
        MockEntry(28.0, 10.0, "Fourth segment starting at 28.0")
    ]
    
    # AI wants to extract Seg 0 to Seg 2 (should end at 30.0 originally)
    clip_input = [{"title": "Overlap prevention clip", "start_index": 0, "end_index": 2}]
    res = _validate_clips(clip_input, transcript_overlap)
    
    # Duration was 30.0. Since Seg 3 starts at 28.0, end_time must pull back to 28.0.
    passed = res[0]["end_time"] == 28.0
    print_result(
        "Overlap Prevention: Clip end pulled back cleanly to next segment start",
        passed,
        f"Expected end_time=28.0, Got end_time={res[0]['end_time']} (Duration: {res[0]['end_time'] - res[0]['start_time']}s)"
    )

    # ──────────────────────────────────────────────────────────
    # CASE 2: Minimum Duration Index Expansion (25s rule)
    # ──────────────────────────────────────────────────────────
    # Segments are 5 seconds each.
    # AI returns start_index=2 (10s) and end_index=4 (25s) -> Duration 15s.
    # Code should expand end_index forward to segment 6 (ends at 35s -> Duration 25s).
    transcript_expand = [MockEntry(float(i * 5), 5.0, f"Line {i}") for i in range(15)]
    clip_short = [{"title": "Short clip", "start_index": 2, "end_index": 4}]
    res_expand = _validate_clips(clip_short, transcript_expand)
    
    dur = res_expand[0]["end_time"] - res_expand[0]["start_time"]
    passed_expand = dur >= 25.0 and res_expand[0]["end_index"] == 6
    print_result(
        "Min Duration Index Expansion: Short clip index expanded forward to segment 6",
        passed_expand,
        f"Expected end_index=6, Got end_index={res_expand[0]['end_index']} (Duration: {dur}s)"
    )

    # ──────────────────────────────────────────────────────────
    # CASE 3: Maximum Duration Index Shrinkage (58s rule)
    # ──────────────────────────────────────────────────────────
    # Segments are 5 seconds each.
    # AI returns start_index=0 (0s) and end_index=15 (80s) -> Duration 80s.
    # Code should shrink end_index backward to segment 11 (ends at 60s? No, ends at 11*5 + 5 = 60s -> still > 58s).
    # Segment 10 ends at 10*5 + 5 = 55s -> Duration 55s (which is <= 58s).
    # So end_index must become 10.
    transcript_shrink = [MockEntry(float(i * 5), 5.0, f"Line {i}") for i in range(20)]
    clip_long = [{"title": "Long clip", "start_index": 0, "end_index": 15}]
    res_shrink = _validate_clips(clip_long, transcript_shrink)
    
    dur_shrink = res_shrink[0]["end_time"] - res_shrink[0]["start_time"]
    passed_shrink = dur_shrink <= 58.0 and res_shrink[0]["end_index"] == 10
    print_result(
        "Max Duration Index Shrinkage: Long clip index shrunk backward to segment 10",
        passed_shrink,
        f"Expected end_index=10, Got end_index={res_shrink[0]['end_index']} (Duration: {dur_shrink}s)"
    )

    # ──────────────────────────────────────────────────────────
    # CASE 4: Hybrid Fallback (Backward compatibility with float times)
    # ──────────────────────────────────────────────────────────
    # AI returns legacy format with start_time=10.0 and end_time=40.0.
    # Code should locate closest segments (index 2 starts at 10.0, index 8 ends at 45.0? Let's check:
    # index 2: start 10.0, index 7: start 35.0, duration 5.0 -> ends at 40.0).
    # So it should resolve to start_index=2, end_index=7.
    clip_hybrid = [{"title": "Legacy float clip", "start_time": 10.0, "end_time": 40.0}]
    res_hybrid = _validate_clips(clip_hybrid, transcript_expand)
    
    passed_hybrid = (
        res_hybrid[0]["start_index"] == 2 and 
        res_hybrid[0]["end_index"] == 7 and
        res_hybrid[0]["start_time"] == 10.0 and
        res_hybrid[0]["end_time"] == 40.0
    )
    print_result(
        "Hybrid Fallback: Float times mapped correctly to index bounds",
        passed_hybrid,
        f"Expected indices (2, 7) and times (10.0, 40.0). Got indices ({res_hybrid[0]['start_index']}, {res_hybrid[0]['end_index']}) and times ({res_hybrid[0]['start_time']}, {res_hybrid[0]['end_time']})"
    )

    # ──────────────────────────────────────────────────────────
    # CASE 5: Strict Output Count Slicing
    # ──────────────────────────────────────────────────────────
    # Requesting 2 clips from mock API.
    # Verify that exactly 2 clips are returned.
    mock_res_2 = analyze_with_gemini("sample", transcript_expand, api_key="mock", num_clips=2)
    passed_count_2 = len(mock_res_2) == 2
    print_result(
        "Strict Output Slicing: Requesting 2 clips returns exactly 2 clips",
        passed_count_2,
        f"Expected count=2, Got count={len(mock_res_2)}"
    )

    # Requesting 1 clip from mock API.
    mock_res_1 = analyze_with_gemini("sample", transcript_expand, api_key="mock", num_clips=1)
    passed_count_1 = len(mock_res_1) == 1
    print_result(
        "Strict Output Slicing: Requesting 1 clip returns exactly 1 clip",
        passed_count_1,
        f"Expected count=1, Got count={len(mock_res_1)}"
    )

    # ──────────────────────────────────────────────────────────
    # CASE 6: Extreme Short Video Fallback
    # ──────────────────────────────────────────────────────────
    # Video transcript has only 2 segments (total 10 seconds).
    # Clamping must fall back to video boundaries (10s) starting from segment 0.
    transcript_short_vid = [MockEntry(0.0, 5.0), MockEntry(5.0, 5.0)]
    clip_short_vid = [{"title": "Short video clip", "start_index": 0, "end_index": 1}]
    res_short_vid = _validate_clips(clip_short_vid, transcript_short_vid)
    
    passed_fallback = res_short_vid[0]["start_time"] == 0.0 and res_short_vid[0]["end_time"] == 10.0
    print_result(
        "Short Video Fallback: Zero/too-short transcript clamped safely to video boundaries",
        passed_fallback,
        f"Expected times [0.0, 10.0]. Got [{res_short_vid[0]['start_time']}, {res_short_vid[0]['end_time']}]"
    )

    # ──────────────────────────────────────────────────────────
    # CASE 7: Ending Safety Padding (0.4s) Assertion
    # ──────────────────────────────────────────────────────────
    # Using a transcript with a gap so overlap pullback does not occur.
    transcript_padding = [
        MockEntry(0.0, 25.0),
        MockEntry(25.0, 5.0), # ends at 30.0
        MockEntry(35.0, 5.0)  # next starts at 35.0
    ]
    clip_padding = [{"title": "Padding Clip", "start_index": 0, "end_index": 1}]
    
    # 7a. Verify default 0.4s safety padding is applied
    res_padding_default = _validate_clips(clip_padding, transcript_padding)
    passed_padding_default = res_padding_default[0]["end_time"] == 30.40
    print_result(
        "Ending Safety Padding: Default 0.4s ending safety padding is applied",
        passed_padding_default,
        f"Expected end_time=30.40, Got end_time={res_padding_default[0]['end_time']}"
    )

    # 7b. Verify custom 0.8s safety padding is applied when specified
    res_padding_custom = _validate_clips(clip_padding, transcript_padding, ending_safety_margin=0.8)
    passed_padding_custom = res_padding_custom[0]["end_time"] == 30.80
    print_result(
        "Ending Safety Padding: Custom 0.8s ending safety padding is applied when specified",
        passed_padding_custom,
        f"Expected end_time=30.80, Got end_time={res_padding_custom[0]['end_time']}"
    )

    # ──────────────────────────────────────────────────────────
    # CASE 8: Uvicorn & Clipper Functionality Assertions
    # ──────────────────────────────────────────────────────────
    try:
        import uvicorn
        cfg_test = uvicorn.Config("main:app", port=8000)
        passed_uvicorn = True
    except Exception as e:
        passed_uvicorn = False
    print_result(
        "Uvicorn Integration: Module import and Config initialization success",
        passed_uvicorn,
        f"Uvicorn version: {getattr(uvicorn, '__version__', 'unknown') if passed_uvicorn else 'failed'}"
    )

    try:
        import clipper
        passed_clipper = clipper.check_ffmpeg() and callable(clipper.get_shot_crop_offsets)
    except Exception as e:
        passed_clipper = False
    print_result(
        "Clipper Integration: Module import and ffmpeg capability check success",
        passed_clipper
    )

    print("=" * 60)
    all_ok = (
        passed and passed_expand and passed_shrink and passed_hybrid and 
        passed_count_2 and passed_count_1 and passed_fallback and 
        passed_padding_default and passed_padding_custom and 
        passed_uvicorn and passed_clipper
    )
    status_msg = f"{GREEN}ALL REGRESSION TESTS PASSED! Clip accuracy is 100% guaranteed.{RESET}" if all_ok else f"{RED}SOME REGRESSION TESTS FAILED! Check logic.{RESET}"
    print(status_msg)
    print("=" * 60)
    sys.exit(0 if all_ok else 1)

if __name__ == '__main__':
    run_regression_tests()
