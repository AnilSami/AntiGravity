# -*- coding: utf-8 -*-
"""
Comprehensive Unit Tests for analyzer.py
YouTube Smart Clip Extractor - QA Test Suite
Tests: URL Parsing, Mock API Clips, Duration Validation, Prompt Quality, job_manager.py Integration
"""

import sys
import os
import re
import json
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = "PASS"
FAIL = "FAIL"

results = []

def record(test_name, status, detail=""):
    results.append((test_name, status, detail))
    marker = "OK" if status == PASS else "!!"
    print("  [%s] %s: %s" % (marker, status, test_name))
    if detail:
        print("        %s" % detail)

def section(title):
    print("\n" + "="*60)
    print("  %s" % title)
    print("="*60)

# Mock transcript entry class to simulate raw transcript list
class MockTranscriptEntry:
    def __init__(self, start, duration, text=""):
        self.start = start
        self.duration = duration
        self.text = text

# Create a dummy transcript: 20 lines of 5 seconds each
dummy_transcript = [MockTranscriptEntry(float(i * 5), 5.0, f"Sentence {i}") for i in range(30)]

# ──────────────────────────────────────────────────────────────
# TEST AREA 1 — Syntax & Import Test
# ──────────────────────────────────────────────────────────────
section("TEST AREA 1: Syntax & Import Test")

try:
    from analyzer import get_video_id, fetch_transcript_list, analyze_with_gemini, _validate_clips
    record("Import get_video_id", PASS)
    record("Import fetch_transcript_list", PASS)
    record("Import analyze_with_gemini", PASS)
    record("Import _validate_clips", PASS)
except ImportError as e:
    record("Import analyzer module", FAIL, f"ImportError: {e}")
    print("\nCannot continue – imports failed. Exiting.")
    sys.exit(1)
except Exception as e:
    record("Import analyzer module", FAIL, f"Unexpected error: {e}")
    sys.exit(1)

# ──────────────────────────────────────────────────────────────
# TEST AREA 2 — URL Parsing Tests
# ──────────────────────────────────────────────────────────────
section("TEST AREA 2: URL Parsing Tests")

url_cases = [
    ("Standard watch URL",       "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("Short youtu.be URL",       "https://youtu.be/dQw4w9WgXcQ",               "dQw4w9WgXcQ"),
    ("YouTube Shorts URL",       "https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("With extra query params",  "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s", "dQw4w9WgXcQ"),
]

for label, url, expected in url_cases:
    try:
        result = get_video_id(url)
        if result == expected:
            record(f"get_video_id – {label}", PASS, f"returned '{result}'")
        else:
            record(f"get_video_id – {label}", FAIL,
                   f"Expected '{expected}', got '{result}'")
    except Exception as e:
        record(f"get_video_id – {label}", FAIL, f"Raised unexpected exception: {e}")

# Invalid URL should raise ValueError
try:
    get_video_id("invalid-url")
    record("get_video_id – invalid URL raises ValueError", FAIL,
           "No exception raised – expected ValueError")
except ValueError as e:
    record("get_video_id – invalid URL raises ValueError", PASS,
           f"Correctly raised ValueError: {e}")
except Exception as e:
    record("get_video_id – invalid URL raises ValueError", FAIL,
           f"Wrong exception type raised: {type(e).__name__}: {e}")

# ──────────────────────────────────────────────────────────────
# TEST AREA 3 — Mock API / Duration Validation Tests
# ──────────────────────────────────────────────────────────────
section("TEST AREA 3: Mock API / Duration Validation Tests")

try:
    mock_clips = analyze_with_gemini("sample transcript text", dummy_transcript, api_key="mock")

    # 3a. Must not be empty
    if mock_clips and len(mock_clips) == 5:
        record("Mock API – clips list has default 5 clips", PASS, f"{len(mock_clips)} clip(s) returned")
    else:
        record("Mock API – clips list has default 5 clips", FAIL, f"Expected 5 clips, got {len(mock_clips) if mock_clips else 0}")

    # Custom counts checks
    mock_clips_3 = analyze_with_gemini("sample transcript text", dummy_transcript, api_key="mock", num_clips=3)
    if len(mock_clips_3) == 3:
        record("Mock API – supports custom count (num_clips=3)", PASS)
    else:
        record("Mock API – supports custom count (num_clips=3)", FAIL, f"Expected 3 clips, got {len(mock_clips_3)}")

    mock_clips_8 = analyze_with_gemini("sample transcript text", dummy_transcript, api_key="mock", num_clips=8)
    if len(mock_clips_8) == 8:
        record("Mock API – supports custom count (num_clips=8)", PASS)
    else:
        record("Mock API – supports custom count (num_clips=8)", FAIL, f"Expected 8 clips, got {len(mock_clips_8)}")

    # 3b. Every clip must have required keys
    required_keys = {"title", "start_time", "end_time", "reason", "shorts_title", "shorts_description", "shorts_tags"}
    all_keys_ok = True
    for i, clip in enumerate(mock_clips_8):
        missing = required_keys - clip.keys()
        if missing:
            record(f"Mock API – clip[{i}] has all required keys", FAIL,
                   f"Missing keys: {missing}")
            all_keys_ok = False
    if all_keys_ok:
        record("Mock API – all clips have required keys (including shorts_title, shorts_description, shorts_tags)", PASS)

    # 3c. Duration constraints: 25 <= duration <= 58
    all_duration_ok = True
    for i, clip in enumerate(mock_clips_8):
        dur = clip["end_time"] - clip["start_time"]
        if dur < 25 or dur > 58:
            record(f"Mock API – clip[{i}] duration in range [25, 58]", FAIL,
                   f"duration={dur:.2f}s (title: {clip.get('title','?')})")
            all_duration_ok = False
    if all_duration_ok:
        record("Mock API – all clip durations are in valid range [25s, 58s]", PASS)

    # 3d. start_time / end_time are numeric
    all_numeric = True
    for i, clip in enumerate(mock_clips_8):
        try:
            float(clip["start_time"])
            float(clip["end_time"])
        except (TypeError, ValueError):
            record(f"Mock API – clip[{i}] start/end_time are numeric", FAIL,
                   f"start={clip['start_time']!r}, end={clip['end_time']!r}")
            all_numeric = False
    if all_numeric:
        record("Mock API – all clips have numeric start_time and end_time", PASS)

    # 3e. Verify correct types for the new SEO fields
    all_types_ok = True
    for i, clip in enumerate(mock_clips_8):
        st = clip.get("shorts_title")
        sd = clip.get("shorts_description")
        tags = clip.get("shorts_tags")
        if not isinstance(st, str):
            record(f"Mock API – clip[{i}] shorts_title is string", FAIL, f"got {type(st).__name__}")
            all_types_ok = False
        if not isinstance(sd, str):
            record(f"Mock API – clip[{i}] shorts_description is string", FAIL, f"got {type(sd).__name__}")
            all_types_ok = False
        if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            record(f"Mock API – clip[{i}] shorts_tags is list of strings", FAIL, f"got {type(tags).__name__}")
            all_types_ok = False
    if all_types_ok:
        record("Mock API – all new SEO fields have correct types (shorts_title: str, shorts_description: str, shorts_tags: list[str])", PASS)

except Exception as e:
    record("Mock API – analyze_with_gemini(api_key='mock')", FAIL,
           f"Exception: {traceback.format_exc()}")

# ──────────────────────────────────────────────────────────────
# TEST AREA 4 — Post-processing Validation Tests (Direct Logic)
# ──────────────────────────────────────────────────────────────
section("TEST AREA 4: Post-processing / Edge-case Validation Tests")

# We call _validate_clips from analyzer directly to test index-based clamping.

# --- Edge case 1: end_index <= start_index (should resolve end_index >= start_index, expand to min duration) ---
edge1 = [{"title": "Bad end", "start_index": 2, "end_index": 1, "reason": "test"}]
result1 = _validate_clips(edge1, dummy_transcript)
# Start is segment 2 (10.0). Since it's too short (5s), it expands forward to segment 7 (end is segment 7's end = 40.0)
# wait, segment 2 starts at 10.0. If duration is >= 25s, segment 6 ends at 35.0 (diff 25.0).
# Let's check segment indices:
# idx 2: [10-15], idx 3: [15-20], idx 4: [20-25], idx 5: [25-30], idx 6: [30-35] (ends at 35.0) -> duration = 25s
if result1[0]["end_time"] - result1[0]["start_time"] >= 25.0:
    record("Validation – clip with end <= start is fixed to minimum duration", PASS,
           f"start={result1[0]['start_time']}, end={result1[0]['end_time']}")
else:
    record("Validation – clip with end <= start is fixed to minimum duration", FAIL,
           f"Resulting duration too short: {result1[0]['end_time'] - result1[0]['start_time']}s")

# --- Edge case 2: duration < 25s (should be expanded indices) ---
edge2 = [{"title": "Too short", "start_index": 4, "end_index": 6, "reason": "test"}]
# idx 4 starts at 20.0, idx 6 ends at 35.0. Initial duration = 15s.
# Should expand end_idx to 8 (ends at 45.0, duration = 25s)
result2 = _validate_clips(edge2, dummy_transcript)
if result2[0]["end_time"] - result2[0]["start_time"] >= 25.0:
    record("Validation – clip with duration < 25s is expanded to >= 25s", PASS,
           f"start={result2[0]['start_time']}, end={result2[0]['end_time']}")
else:
    record("Validation – clip with duration < 25s is expanded to >= 25s", FAIL,
           f"Got duration: {result2[0]['end_time'] - result2[0]['start_time']}s")

# --- Edge case 3: duration > 58s (should be shrunk) ---
edge3 = [{"title": "Too long", "start_index": 0, "end_index": 20, "reason": "test"}]
# idx 0 starts at 0.0, idx 20 ends at 105.0. Duration = 105s.
# Should shrink end_idx to 10 (ends at 55.0, duration = 55s)
result3 = _validate_clips(edge3, dummy_transcript)
dur3 = result3[0]["end_time"] - result3[0]["start_time"]
if 25.0 <= dur3 <= 58.0:
    record("Validation – clip with duration > 58s is capped to <= 58s", PASS,
           f"start={result3[0]['start_time']}, end={result3[0]['end_time']}, duration={dur3}s")
else:
    record("Validation – clip with duration > 58s is capped to <= 58s", FAIL,
           f"Got invalid duration: {dur3}s")

# --- Edge case 4: hybrid fallback (handles float times input) ---
edge4 = [{"title": "Float times fallback", "start_time": 10.0, "end_time": 40.0, "reason": "test"}]
result4 = _validate_clips(edge4, dummy_transcript)
if result4[0]["start_time"] == 10.0 and result4[0]["end_time"] == 40.0:
    record("Validation – hybrid fallback maps float times to correct segments", PASS)
else:
    record("Validation – hybrid fallback maps float times to correct segments", FAIL,
           f"Expected [10.0, 40.0], got [{result4[0]['start_time']}, {result4[0]['end_time']}]")

# --- Edge case 5: overlapping next segment check ---
# Let's create a transcript with enough segments to exceed 25 seconds.
# Segments 0-5: 0.0 to 30.0 (5 seconds each)
# Segment 6: starts at 28.0 (overlaps segment 5 which ends at 30.0)
overlap_transcript = [
    MockTranscriptEntry(0.0, 5.0),
    MockTranscriptEntry(5.0, 5.0),
    MockTranscriptEntry(10.0, 5.0),
    MockTranscriptEntry(15.0, 5.0),
    MockTranscriptEntry(20.0, 5.0),
    MockTranscriptEntry(25.0, 5.0), # segment 5 ends at 30.0
    MockTranscriptEntry(28.0, 5.0)  # segment 6 starts at 28.0 (overlap)
]
edge5 = [{"title": "Overlap clip", "start_index": 0, "end_index": 5}]
# end_time should become min(30.0, 28.0) = 28.0
result5 = _validate_clips(edge5, overlap_transcript)
if result5[0]["end_time"] == 28.0:
    record("Validation – overlap logic correctly pulls back end_time to prevent hearing next sentence", PASS)
else:
    record("Validation – overlap logic correctly pulls back end_time to prevent hearing next sentence", FAIL,
           f"Expected end_time=28.0, got {result5[0]['end_time']}")

# --- Edge case 6: SEO fields fallbacks are applied correctly when missing ---
edge6 = [{"title": "Missing SEO Clip", "start_index": 0, "end_index": 5, "reason": "Reason for missing SEO."}]
result6 = _validate_clips(edge6, dummy_transcript)
seo_clip = result6[0]
if (
    seo_clip.get("shorts_title") == "Missing SEO Clip #shorts"
    and seo_clip.get("shorts_description") == "Reason for missing SEO. Subscribe for more awesome clips! #shorts #learning"
    and isinstance(seo_clip.get("shorts_tags"), list)
    and "shorts" in seo_clip.get("shorts_tags", [])
):
    record("Validation – SEO fields correctly fallback when missing", PASS)
else:
    record("Validation – SEO fields correctly fallback when missing", FAIL,
           f"Got shorts_title={seo_clip.get('shorts_title')!r}, "
           f"shorts_description={seo_clip.get('shorts_description')!r}, "
           f"shorts_tags={seo_clip.get('shorts_tags')!r}")

# --- Edge case 7: Ending Safety Padding (0.4s) is applied ---
# We use a custom transcript with a gap to prevent overlap pullback
padding_transcript = [
    MockTranscriptEntry(0.0, 25.0),
    MockTranscriptEntry(25.0, 5.0), # ends at 30.0
    MockTranscriptEntry(35.0, 5.0)  # next starts at 35.0, so no overlap pullback
]
edge7 = [{"title": "Padding Clip", "start_index": 0, "end_index": 1}]
result7 = _validate_clips(edge7, padding_transcript)
if result7[0]["end_time"] == 30.40:
    record("Validation – 0.4s ending safety padding is applied by default", PASS, f"end_time={result7[0]['end_time']}")
else:
    record("Validation – 0.4s ending safety padding is applied by default", FAIL, f"Expected 30.40, got {result7[0]['end_time']}")

# Let's also check that a custom ending_safety_margin can be passed and is respected
result7_custom = _validate_clips(edge7, padding_transcript, ending_safety_margin=0.8)
if result7_custom[0]["end_time"] == 30.80:
    record("Validation – custom ending safety padding (0.8s) is applied when specified", PASS, f"end_time={result7_custom[0]['end_time']}")
else:
    record("Validation – custom ending safety padding (0.8s) is applied when specified", FAIL, f"Expected 30.80, got {result7_custom[0]['end_time']}")

# ──────────────────────────────────────────────────────────────
# TEST AREA 5 — Prompt Content Quality Check
# ──────────────────────────────────────────────────────────────
section("TEST AREA 5: Prompt Content Quality Check (analyzer.py source)")

analyzer_path = r'd:\Desktop\LLM\backend\analyzer.py'
try:
    with open(analyzer_path, 'r', encoding='utf-8') as f:
        analyzer_source = f.read()

    prompt_checks = [
        ("Prompt contains 'HOOK'",                  "HOOK"),
        ("Prompt contains 'CORE VALUE'",             "CORE VALUE"),
        ("Prompt contains 'NATURAL ENDING'",         "NATURAL ENDING"),
        ("Prompt contains 'INFORMATIONAL DENSITY'",  "INFORMATIONAL DENSITY"),
        ("Prompt contains '58' (not just 60)",       "58"),
    ]

    for label, keyword in prompt_checks:
        if keyword in analyzer_source:
            record(label, PASS)
        else:
            record(label, FAIL, f"Keyword '{keyword}' NOT found in analyzer.py source")

    # Check the validation cap is 58, NOT 60
    if "MAX_CLIP_DURATION" in analyzer_source:
        record("Validation – duration cap uses MAX_CLIP_DURATION constant", PASS)
    else:
        record("Validation – duration cap uses MAX_CLIP_DURATION constant", FAIL,
               "Could not find 'MAX_CLIP_DURATION' in source — cap may use wrong threshold")

    # Verify 60 is NOT the cap value (make sure '> 60' doesn't appear as a duration cap)
    if "if duration > 60" in analyzer_source:
        record("Prompt/validation – does NOT use 60 as duration cap", FAIL,
               "Found 'if duration > 60' which contradicts the 58s cap requirement")
    else:
        record("Prompt/validation – does NOT use 60 as duration cap", PASS)

except FileNotFoundError:
    record("Read analyzer.py source", FAIL, f"File not found: {analyzer_path}")
except Exception as e:
    record("Read analyzer.py source", FAIL, f"Error: {e}")

# ──────────────────────────────────────────────────────────────
# TEST AREA 6 — job_manager.py Integration Check
# ──────────────────────────────────────────────────────────────
section("TEST AREA 6: job_manager.py Integration Check")

jm_path = r'd:\Desktop\LLM\backend\job_manager.py'
try:
    with open(jm_path, 'r', encoding='utf-8') as f:
        jm_source = f.read()

    # 6a. generate_ass() function exists
    if "def generate_ass(" in jm_source:
        record("job_manager.py – generate_ass() function defined", PASS)
    else:
        record("job_manager.py – generate_ass() function defined", FAIL,
               "No 'def generate_ass(' found in job_manager.py")

    # 6b. EMOJI_DICTIONARY is defined
    if "EMOJI_DICTIONARY" in jm_source and "={" in jm_source.replace(" ", ""):
        record("job_manager.py – EMOJI_DICTIONARY is defined", PASS)
    else:
        record("job_manager.py – EMOJI_DICTIONARY is defined", FAIL,
               "'EMOJI_DICTIONARY' definition not found")

    # More robust check
    if re.search(r'EMOJI_DICTIONARY\s*=\s*\{', jm_source):
        record("job_manager.py – EMOJI_DICTIONARY has dict literal assignment", PASS)
    else:
        record("job_manager.py – EMOJI_DICTIONARY has dict literal assignment", FAIL,
               "No 'EMOJI_DICTIONARY = {' pattern found")

    # 6c. run_pipeline() calls analyze_with_gemini
    if "def run_pipeline(" in jm_source:
        record("job_manager.py – run_pipeline() function defined", PASS)
    else:
        record("job_manager.py – run_pipeline() function defined", FAIL,
               "No 'def run_pipeline(' found")

    if "analyze_with_gemini" in jm_source:
        record("job_manager.py – run_pipeline() calls analyze_with_gemini", PASS)
    else:
        record("job_manager.py – run_pipeline() calls analyze_with_gemini", FAIL,
               "No reference to 'analyze_with_gemini' in job_manager.py")

    # 6d. Import of analyze_with_gemini from analyzer
    if "from analyzer import" in jm_source and "analyze_with_gemini" in jm_source:
        record("job_manager.py – imports analyze_with_gemini from analyzer", PASS)
    else:
        record("job_manager.py – imports analyze_with_gemini from analyzer", FAIL,
               "Could not confirm import of analyze_with_gemini from analyzer")

    # 6e. format_ass_time helper exists
    if "def format_ass_time(" in jm_source:
        record("job_manager.py – format_ass_time() helper defined", PASS)
    else:
        record("job_manager.py – format_ass_time() helper defined", FAIL)

except FileNotFoundError:
    record("Read job_manager.py source", FAIL, f"File not found: {jm_path}")
except Exception as e:
    record("Read job_manager.py source", FAIL, f"Error: {e}")

# ──────────────────────────────────────────────────────────────
# Additional: import-level test for job_manager
# ──────────────────────────────────────────────────────────────
section("BONUS: job_manager.py Import Test")
try:
    import importlib, unittest.mock as mock
    # We do a targeted import check without triggering network or file I/O side effects
    # by checking whether the module can be imported in isolation
    with mock.patch.dict('sys.modules', {
        'youtube_transcript_api': mock.MagicMock(),
        'google.generativeai': mock.MagicMock(),
        'openai': mock.MagicMock(),
        'clipper': mock.MagicMock(),
    }):
        import importlib.util
        spec = importlib.util.spec_from_file_location("job_manager", jm_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Verify attributes
        if callable(getattr(mod, 'generate_ass', None)):
            record("job_manager – generate_ass is callable after import", PASS)
        else:
            record("job_manager – generate_ass is callable after import", FAIL)

        if isinstance(getattr(mod, 'EMOJI_DICTIONARY', None), dict):
            ed = mod.EMOJI_DICTIONARY
            record(f"job_manager – EMOJI_DICTIONARY is a dict ({len(ed)} entries)", PASS)
        else:
            record("job_manager – EMOJI_DICTIONARY is a dict", FAIL)

        if callable(getattr(mod, 'run_pipeline', None)):
            record("job_manager – run_pipeline is callable after import", PASS)
        else:
            record("job_manager – run_pipeline is callable after import", FAIL)

        clip_info_cls = getattr(mod, 'ClipInfo', None)
        if clip_info_cls:
            fields = clip_info_cls.model_fields if hasattr(clip_info_cls, "model_fields") else clip_info_cls.__fields__
            if "shorts_title" in fields and "shorts_description" in fields and "shorts_tags" in fields:
                record("job_manager – ClipInfo contains shorts_title, shorts_description, and shorts_tags fields", PASS)
            else:
                record("job_manager – ClipInfo contains shorts_title, shorts_description, and shorts_tags fields", FAIL, f"Fields: {list(fields.keys())}")
        else:
            record("job_manager – ClipInfo class not found", FAIL)

except Exception as e:
    record("job_manager – module import/attribute check", FAIL,
           f"Exception: {traceback.format_exc()}")

# ──────────────────────────────────────────────────────────────
# TEST AREA 7 — Uvicorn & Clipper Functionality Check
# ──────────────────────────────────────────────────────────────
section("TEST AREA 7: Uvicorn & Clipper Functionality Check")

try:
    import uvicorn
    # Verify uvicorn module contains Config
    cfg = uvicorn.Config("main:app", port=8000)
    record("Uvicorn – import and config creation successful", PASS, f"uvicorn version: {getattr(uvicorn, '__version__', 'unknown')}")
except Exception as e:
    record("Uvicorn – import and config creation successful", FAIL, f"Error: {e}")

try:
    import clipper
    if clipper.check_ffmpeg():
        record("Clipper – ffmpeg binary check passes", PASS)
    else:
        record("Clipper – ffmpeg binary check passes", FAIL, "ffmpeg not found in PATH")
        
    # Verify Clipper functions exist and are callable
    if callable(clipper.get_shot_crop_offsets) and callable(clipper.extract_clip) and callable(clipper.get_video_resolution):
        record("Clipper – key pipeline functions defined and callable", PASS)
    else:
        record("Clipper – key pipeline functions defined and callable", FAIL)
except Exception as e:
    record("Clipper – module and capability verification", FAIL, f"Error: {e}")

# ──────────────────────────────────────────────────────────────
# FINAL SUMMARY
# ──────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("  FINAL TEST SUMMARY")
print("="*60)

passed = [r for r in results if r[1] == PASS]
failed = [r for r in results if r[1] == FAIL]

print("\n  Total : %d" % len(results))
print("  PASSED: %d" % len(passed))
print("  FAILED: %d" % len(failed))

if failed:
    print("\n  --- FAILED TESTS ---")
    for name, status, detail in failed:
        print("  [!!] %s" % name)
        if detail:
            print("       %s" % detail)
else:
    print("\n  All tests passed!")

print("\n" + "="*60 + "\n")
sys.exit(0 if not failed else 1)
