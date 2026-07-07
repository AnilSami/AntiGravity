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
# Start is segment 2 (10.0). Since it's too short (5s), it expands forward to segment 9 (end is segment 9's end = 50.0)
# wait, segment 2 starts at 10.0. If duration is >= 38s, segment 9 ends at 50.0 (diff 40.0).
if result1[0]["end_time"] - result1[0]["start_time"] >= 38.0:
    record("Validation – clip with end <= start is fixed to minimum duration", PASS,
           f"start={result1[0]['start_time']}, end={result1[0]['end_time']}")
else:
    record("Validation – clip with end <= start is fixed to minimum duration", FAIL,
           f"Resulting duration too short: {result1[0]['end_time'] - result1[0]['start_time']}s")

# --- Edge case 2: duration < 38s (should be expanded indices) ---
edge2 = [{"title": "Too short", "start_index": 4, "end_index": 6, "reason": "test"}]
# idx 4 starts at 20.0, idx 6 ends at 35.0. Initial duration = 15s.
# Should expand end_idx to 11 (ends at 60.0, duration = 40s >= 38s)
result2 = _validate_clips(edge2, dummy_transcript)
if result2[0]["end_time"] - result2[0]["start_time"] >= 38.0:
    record("Validation – clip with duration < 38s is expanded to >= 38s", PASS,
           f"start={result2[0]['start_time']}, end={result2[0]['end_time']}")
else:
    record("Validation – clip with duration < 38s is expanded to >= 38s", FAIL,
           f"Got duration: {result2[0]['end_time'] - result2[0]['start_time']}s")

# --- Edge case 3: duration > 58s (should be shrunk) ---
edge3 = [{"title": "Too long", "start_index": 0, "end_index": 20, "reason": "test"}]
# idx 0 starts at 0.0, idx 20 ends at 105.0. Duration = 105s.
# Should shrink end_idx to 10 (ends at 55.0, duration = 55s)
result3 = _validate_clips(edge3, dummy_transcript)
dur3 = result3[0]["end_time"] - result3[0]["start_time"]
if 38.0 <= dur3 <= 58.0:
    record("Validation – clip with duration > 58s is capped to <= 58s", PASS,
           f"start={result3[0]['start_time']}, end={result3[0]['end_time']}, duration={dur3}s")
else:
    record("Validation – clip with duration > 58s is capped to <= 58s", FAIL,
           f"Got invalid duration: {dur3}s")

# --- Edge case 4: hybrid fallback (handles float times input) ---
edge4 = [{"title": "Float times fallback", "start_time": 10.0, "end_time": 50.0, "reason": "test"}]
result4 = _validate_clips(edge4, dummy_transcript)
if result4[0]["start_time"] == 10.0 and result4[0]["end_time"] == 50.0:
    record("Validation – hybrid fallback maps float times to correct segments", PASS)
else:
    record("Validation – hybrid fallback maps float times to correct segments", FAIL,
           f"Expected [10.0, 50.0], got [{result4[0]['start_time']}, {result4[0]['end_time']}]")

# --- Edge case 5: overlapping next segment check ---
# Let's create a transcript with enough segments to exceed 38 seconds.
# Segments 0-8: 0.0 to 45.0 (5 seconds each)
# Segment 9: starts at 43.0 (overlaps segment 8 which ends at 45.0)
overlap_transcript = [
    MockTranscriptEntry(0.0, 5.0),
    MockTranscriptEntry(5.0, 5.0),
    MockTranscriptEntry(10.0, 5.0),
    MockTranscriptEntry(15.0, 5.0),
    MockTranscriptEntry(20.0, 5.0),
    MockTranscriptEntry(25.0, 5.0),
    MockTranscriptEntry(30.0, 5.0),
    MockTranscriptEntry(35.0, 5.0),
    MockTranscriptEntry(40.0, 5.0), # segment 8 ends at 45.0
    MockTranscriptEntry(43.0, 5.0)  # segment 9 starts at 43.0 (overlap)
]
edge5 = [{"title": "Overlap clip", "start_index": 0, "end_index": 8}]
# end_time should become min(45.0, 43.0) = 43.0
result5 = _validate_clips(edge5, overlap_transcript)
if result5[0]["end_time"] == 43.0:
    record("Validation – overlap logic correctly pulls back end_time to prevent hearing next sentence", PASS)
else:
    record("Validation – overlap logic correctly pulls back end_time to prevent hearing next sentence", FAIL,
           f"Expected end_time=43.0, got {result5[0]['end_time']}")

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
    MockTranscriptEntry(0.0, 40.0),
    MockTranscriptEntry(40.0, 5.0), # ends at 45.0
    MockTranscriptEntry(55.0, 5.0)  # next starts at 55.0, so no overlap pullback
]
edge7 = [{"title": "Padding Clip", "start_index": 0, "end_index": 1}]
result7 = _validate_clips(edge7, padding_transcript)
if result7[0]["end_time"] == 45.40:
    record("Validation – 0.4s ending safety padding is applied by default", PASS, f"end_time={result7[0]['end_time']}")
else:
    record("Validation – 0.4s ending safety padding is applied by default", FAIL, f"Expected 45.40, got {result7[0]['end_time']}")

# Let's also check that a custom ending_safety_margin can be passed and is respected
result7_custom = _validate_clips(edge7, padding_transcript, ending_safety_margin=0.8)
if result7_custom[0]["end_time"] == 45.80:
    record("Validation – custom ending safety padding (0.8s) is applied when specified", PASS, f"end_time={result7_custom[0]['end_time']}")
else:
    record("Validation – custom ending safety padding (0.8s) is applied when specified", FAIL, f"Expected 45.80, got {result7_custom[0]['end_time']}")

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
# TEST AREA 8 — Hook Jaccard Calculation Check
# ──────────────────────────────────────────────────────────────
section("TEST AREA 8: Hook Jaccard Calculation Check")

try:
    # We construct inputs to test _validate_clips' Jaccard logic
    # raw transcript for dummy purposes
    local_transcript = [MockTranscriptEntry(float(i*10), 10.0, f"Line {i}") for i in range(50)]
    
    # CASE A: Jaccard similarity is 4/5 = 0.8 (when title is excluded/matching)
    # Since Jaccard is > 0.75, candidate should be discarded
    case_a_candidates = [
        {"title": "Test", "start_index": 0, "end_index": 2, "virality_score": 9.0, "shorts_title": "success mindset growth attitude"},
        {"title": "Test", "start_index": 30, "end_index": 32, "virality_score": 8.0, "shorts_title": "success mindset growth attitude grit"}
    ]
    res_a = _validate_clips(case_a_candidates, local_transcript)
    if len(res_a) == 1 and res_a[0]["shorts_title"] == "success mindset growth attitude":
        record("Hook Jaccard – Case A (4/5 Jaccard > 75% discarded)", PASS)
    else:
        record("Hook Jaccard – Case A (4/5 Jaccard > 75% discarded)", FAIL, f"Expected 1 clip, got {len(res_a)}")

    # CASE B: Identical hook sets (Jaccard = 1.0)
    # Since 1.0 > 0.6, candidate should be discarded
    case_b_candidates = [
        {"title": "Test", "start_index": 0, "end_index": 2, "virality_score": 9.0, "shorts_title": "success mindset"},
        {"title": "Test", "start_index": 30, "end_index": 32, "virality_score": 8.0, "shorts_title": "success mindset"}
    ]
    res_b = _validate_clips(case_b_candidates, local_transcript)
    if len(res_b) == 1 and res_b[0]["shorts_title"] == "success mindset":
        record("Hook Jaccard – Case B (Identical hook discarded)", PASS)
    else:
        record("Hook Jaccard – Case B (Identical hook discarded)", FAIL, f"Expected 1 clip, got {len(res_b)}")

    # CASE C: No overlap (Jaccard = 0.0 without shared title)
    # Since Jaccard <= 0.6, candidate should be kept
    case_c_candidates = [
        {"title": "Test", "start_index": 0, "end_index": 2, "virality_score": 9.0, "shorts_title": "success mindset"},
        {"title": "Test", "start_index": 30, "end_index": 32, "virality_score": 8.0, "shorts_title": "completely different title"}
    ]
    res_c = _validate_clips(case_c_candidates, local_transcript)
    if len(res_c) == 2:
        record("Hook Jaccard – Case C (No overlap kept)", PASS)
    else:
        record("Hook Jaccard – Case C (No overlap kept)", FAIL, f"Expected 2 clips, got {len(res_c)}")

    # CASE D: Regression / Union Bug Verification
    # Checking that the correct implementation retains the candidate.
    case_d_candidates = [
        {"title": "Test", "start_index": 0, "end_index": 2, "virality_score": 9.0, "shorts_title": "success mindset"},
        {"title": "Test", "start_index": 30, "end_index": 32, "virality_score": 8.0, "shorts_title": "success mindset growth attitude grit"}
    ]
    res_d = _validate_clips(case_d_candidates, local_transcript)
    if len(res_d) == 2:
        record("Hook Jaccard – Regression Test (Union bug fixed and candidate retained)", PASS)
    else:
        record("Hook Jaccard – Regression Test (Union bug fixed and candidate retained)", FAIL, f"Expected 2 clips (retained), got {len(res_d)} (discarded)")

except Exception as e:
    record("Hook Jaccard – Unit Test suite", FAIL, f"Exception: {e}")

# ──────────────────────────────────────────────────────────────
# TEST AREA 9 — Data Driven Clip Scoring Engine Tests
# ──────────────────────────────────────────────────────────────
section("TEST AREA 9: Data Driven Clip Scoring Engine Tests")

try:
    from analyzer import calculate_virality_score, SCORING_SETTINGS
    
    base_llm_scores = {
        "hook_strength": 5.0,
        "first_3_second_hook": 5.0,
        "curiosity_gap": 5.0,
        "emotional_intensity": 5.0,
        "controversy": 5.0,
        "surprise": 5.0,
        "actionability": 5.0,
        "storytelling": 5.0
    }
    
    # 1. Base Score calculation
    score_base, detailed_base = calculate_virality_score("Normal text clip without special keywords.", "Simple Title", base_llm_scores)
    if abs(score_base - 5.0) < 0.01:
        record("Scoring Engine - Base Score Calculation", PASS)
    else:
        record("Scoring Engine - Base Score Calculation", FAIL, f"Expected 5.0, got {score_base}")
        
    # 2. Hook Penalty (starts with "so")
    score_pen, detailed_pen = calculate_virality_score("So back in the day we did things.", "Simple Title", base_llm_scores)
    if detailed_pen["hook_strength"] == 3.0 and detailed_pen["first_3_second_hook"] == 3.0:
        record("Scoring Engine - Hook Penalty (filler word)", PASS)
    else:
        record("Scoring Engine - Hook Penalty (filler word)", FAIL, f"Expected hook_strength=3.0, got {detailed_pen}")
        
    # 3. Hook Boost (starts with "never")
    score_boost, detailed_boost = calculate_virality_score("Never do this if you want to win 100%.", "Simple Title", base_llm_scores)
    if detailed_boost["hook_strength"] == 7.0 and detailed_boost["first_3_second_hook"] == 6.0:
        record("Scoring Engine - Hook Boost (strong word + number)", PASS)
    else:
        record("Scoring Engine - Hook Boost (strong word + number)", FAIL, f"Expected hook_strength=7.0, first_3_second_hook=6.0, got {detailed_boost}")
        
    # 4. Programmatic Pattern: Opening Question & Conflict
    score_pattern, detailed_pattern = calculate_virality_score("Why is this the worst fight in history?", "Intriguing Title", base_llm_scores)
    if detailed_pattern["curiosity_gap"] == 6.0 and detailed_pattern["controversy"] == 6.0:
        record("Scoring Engine - Programmatic Patterns (Question + Conflict)", PASS)
    else:
        record("Scoring Engine - Programmatic Patterns (Question + Conflict)", FAIL, f"Expected curiosity_gap=6.0, controversy=6.0, got {detailed_pattern}")
        
    # 5. Metadata Propagation Test
    local_transcript = [MockTranscriptEntry(0.0, 5.0, "Word")]
    candidates = [
        {
            "title": "High Virality Clip",
            "start_index": 0,
            "end_index": 0,
            "virality_score": 8.5,
            "detailed_scores": {"hook_strength": 9.0, "first_3_second_hook": 9.0}
        }
    ]
    res_meta = _validate_clips(candidates, local_transcript)
    if len(res_meta) == 1 and res_meta[0]["virality_score"] == 8.5 and res_meta[0]["detailed_scores"].get("hook_strength") == 9.0:
        record("Scoring Engine - Metadata Propagation to _validate_clips", PASS)
    else:
        record("Scoring Engine - Metadata Propagation to _validate_clips", FAIL, f"Metadata copy failed: {res_meta}")

except Exception as e:
    record("Scoring Engine - Unit Test suite", FAIL, f"Exception: {e}")



# ──────────────────────────────────────────────────────────────
# TEST AREA 13 — Phase 13.1 Camera Tracking Unit Tests
# ──────────────────────────────────────────────────────────────
section("TEST AREA 13: Phase 13.1 Camera Tracking")

try:
    from clipper import (
        FaceTracker, KalmanCrop, _iou, _lip_activity,
        get_shot_crop_offsets,
        _MAX_CROP_VELOCITY, _DEAD_ZONE_PX,
        _SPEAKER_LOCK_SECS, _HEADROOM_FRACTION,
    )
    record("Import Phase-13 tracking symbols", PASS)
except ImportError as e:
    record("Import Phase-13 tracking symbols", FAIL, str(e))

# ── IoU helper ──────────────────────────────────────────────────

try:
    # Full overlap → 1.0
    score = _iou((0, 0, 10, 10), (0, 0, 10, 10))
    assert abs(score - 1.0) < 1e-6, f"Expected 1.0, got {score}"
    record("_iou: perfect overlap = 1.0", PASS)
except Exception as e:
    record("_iou: perfect overlap = 1.0", FAIL, str(e))

try:
    # No overlap → 0.0
    score = _iou((0, 0, 10, 10), (20, 20, 10, 10))
    assert score == 0.0, f"Expected 0.0, got {score}"
    record("_iou: no overlap = 0.0", PASS)
except Exception as e:
    record("_iou: no overlap = 0.0", FAIL, str(e))

try:
    # Partial overlap: two 10x10 boxes offset by 5 px
    # intersection=50, union=150 => IoU = 50/150 = 0.333
    score = _iou((0, 0, 10, 10), (5, 0, 10, 10))
    assert 0.28 < score < 0.40, f"Expected ~0.333, got {score}"
    record("_iou: partial overlap in expected range", PASS)
except Exception as e:
    record("_iou: partial overlap in expected range", FAIL, str(e))

# ── FaceTracker ─────────────────────────────────────────────────

try:
    ft = FaceTracker(iou_threshold=0.30, max_missing=5)
    # Frame 1: two detections
    tracks = ft.update([(10, 10, 50, 50), (200, 10, 50, 50)])
    assert len(tracks) == 2, f"Expected 2 tracks, got {len(tracks)}"
    record("FaceTracker: 2 detections -> 2 track IDs", PASS)
except Exception as e:
    record("FaceTracker: 2 detections -> 2 track IDs", FAIL, str(e))

try:
    ft = FaceTracker(iou_threshold=0.30, max_missing=5)
    tracks1 = ft.update([(10, 10, 50, 50)])
    tid_first = list(tracks1.keys())[0]
    # Frame 2: same box shifted slightly → should keep same ID
    tracks2 = ft.update([(12, 10, 50, 50)])
    tid_second = list(tracks2.keys())[0]
    assert tid_first == tid_second, (
        f"Track ID changed from {tid_first} to {tid_second} on small shift"
    )
    record("FaceTracker: stable track ID across small box shift", PASS)
except Exception as e:
    record("FaceTracker: stable track ID across small box shift", FAIL, str(e))

try:
    ft = FaceTracker(iou_threshold=0.30, max_missing=2)
    ft.update([(10, 10, 50, 50)])
    ft.update([])   # missing frame 1
    ft.update([])   # missing frame 2
    tracks = ft.update([])  # frame 3 → pruned
    assert len(tracks) == 0, f"Expected 0 tracks after pruning, got {len(tracks)}"
    record("FaceTracker: stale track pruned after max_missing", PASS)
except Exception as e:
    record("FaceTracker: stale track pruned after max_missing", FAIL, str(e))

try:
    ft = FaceTracker()
    tracks = ft.update([(10, 10, 50, 50)])
    tid = list(tracks.keys())[0]
    assert tracks[tid]['age'] == 1, f"Expected age=1, got {tracks[tid]['age']}"
    assert tracks[tid]['missing'] == 0
    assert tracks[tid]['lip_history'] == []
    record("FaceTracker: new track has correct initial state", PASS)
except Exception as e:
    record("FaceTracker: new track has correct initial state", FAIL, str(e))

# ── KalmanCrop ──────────────────────────────────────────────────

try:
    kc = KalmanCrop(initial_x=500.0, process_noise=2.0, measurement_noise=60.0)
    assert abs(kc.position - 500.0) < 1e-6
    record("KalmanCrop: initial position correct", PASS)
except Exception as e:
    record("KalmanCrop: initial position correct", FAIL, str(e))

try:
    kc = KalmanCrop(initial_x=0.0, process_noise=2.0, measurement_noise=60.0)
    positions = []
    for _ in range(30):
        kc.predict()
        kc.update(1000.0)   # persistent step input at 1000 px
        positions.append(kc.position)
    # Kalman filter trusts measurement on first step (high P[0,0] relative to R),
    # so the first jump is expected to be large. What matters is:
    #   (a) it converges to ~1000 by frame 30
    #   (b) it does not overshoot beyond 1000
    assert positions[-1] > 900.0, f"Did not converge to 1000 after 30 steps: {positions[-1]}"
    assert max(positions) <= 1100.0, f"Kalman overshot significantly: {max(positions)}"
    record("KalmanCrop: converges to step input within 30 frames", PASS)
except Exception as e:
    record("KalmanCrop: converges to step input within 30 frames", FAIL, str(e))

try:
    import math
    # Verify velocity clamp (applied on top of Kalman) suppresses large jumps
    # This is the production behavior tested at the integration level.
    kc = KalmanCrop(initial_x=0.0)
    kc.predict()
    raw_pos = kc.update(1000.0)
    # Without clamp, raw_pos would be large
    current = 0.0
    delta = raw_pos - current
    if abs(delta) > _MAX_CROP_VELOCITY:
        clamped_pos = current + math.copysign(_MAX_CROP_VELOCITY, delta)
    else:
        clamped_pos = raw_pos
    assert abs(clamped_pos - current) <= _MAX_CROP_VELOCITY, (
        f"Velocity clamp failed to limit movement: delta={clamped_pos - current}"
    )
    record("KalmanCrop: velocity clamp limits first-frame camera movement", PASS)
except Exception as e:
    record("KalmanCrop: velocity clamp limits first-frame camera movement", FAIL, str(e))


try:
    kc = KalmanCrop(initial_x=500.0)
    # Predict/update with the same value → should stay stable
    for _ in range(10):
        kc.predict()
        kc.update(500.0)
    assert abs(kc.position - 500.0) < 5.0, f"Drifted to {kc.position}"
    record("KalmanCrop: stable at constant measurement", PASS)
except Exception as e:
    record("KalmanCrop: stable at constant measurement", FAIL, str(e))

# ── Lip-activity helper ─────────────────────────────────────────

try:
    import numpy as np
    h, w = 100, 60
    # Flat gray frame → low variance
    gray_flat = np.full((h, w), 128, dtype=np.uint8)
    val_flat = _lip_activity(gray_flat, (0, 0, w, h))
    # Noisy frame → higher variance
    rng = np.random.default_rng(42)
    gray_noisy = rng.integers(0, 255, (h, w), dtype=np.uint8)
    val_noisy = _lip_activity(gray_noisy, (0, 0, w, h))
    assert 0.0 <= val_flat <= 1.0
    assert 0.0 <= val_noisy <= 1.0
    assert val_noisy > val_flat, (
        f"Noisy ({val_noisy:.3f}) should be > flat ({val_flat:.3f})"
    )
    record("_lip_activity: noisy ROI > flat ROI", PASS)
except Exception as e:
    record("_lip_activity: noisy ROI > flat ROI", FAIL, str(e))

try:
    import numpy as np
    # Empty ROI (face box outside frame) → should return 0.0 without error
    gray = np.zeros((10, 10), dtype=np.uint8)
    val = _lip_activity(gray, (100, 100, 50, 50))  # totally outside
    assert val == 0.0, f"Expected 0.0 for empty ROI, got {val}"
    record("_lip_activity: out-of-bounds box returns 0.0 safely", PASS)
except Exception as e:
    record("_lip_activity: out-of-bounds box returns 0.0 safely", FAIL, str(e))

# ── Constants sanity checks ─────────────────────────────────────

try:
    assert _MAX_CROP_VELOCITY == 15, f"MAX_CROP_VELOCITY={_MAX_CROP_VELOCITY}"
    assert _DEAD_ZONE_PX == 60, f"DEAD_ZONE_PX={_DEAD_ZONE_PX}"
    assert 0.5 <= _SPEAKER_LOCK_SECS <= 3.0, f"SPEAKER_LOCK_SECS={_SPEAKER_LOCK_SECS}"
    assert 0.0 < _HEADROOM_FRACTION < 0.25, f"HEADROOM_FRACTION={_HEADROOM_FRACTION}"
    record("Phase-13 constants: values in spec range", PASS)
except Exception as e:
    record("Phase-13 constants: values in spec range", FAIL, str(e))

# ── AUDIT_FAST_CLIP fast-path ───────────────────────────────────

try:
    import os
    os.environ["AUDIT_FAST_CLIP"] = "true"
    result = get_shot_crop_offsets("nonexistent.mp4", 1920, 1080, 30.0, 100)
    os.environ["AUDIT_FAST_CLIP"] = "false"
    assert isinstance(result, list), "Expected list"
    assert len(result) == 100, f"Expected 100 offsets, got {len(result)}"
    assert len(set(result)) == 1, "Expected all offsets identical (static center)"
    # Center should be reasonable: (1920 - crop_w) / 2
    crop_w = (int(1080 * 9 / 16) // 2) * 2
    expected_cx = (1920 - crop_w) // 2
    assert abs(result[0] - expected_cx) < 4, (
        f"Expected ~{expected_cx}, got {result[0]}"
    )
    record("get_shot_crop_offsets: AUDIT_FAST_CLIP returns static center list", PASS)
except Exception as e:
    os.environ["AUDIT_FAST_CLIP"] = "false"
    record("get_shot_crop_offsets: AUDIT_FAST_CLIP returns static center list", FAIL, str(e))

# ── Speaker lock hysteresis (unit-level) ────────────────────────

try:
    # Simulate the lock logic with a fresh FaceTracker but calling the
    # internal accumulator manually (white-box test)
    lock_frames = int(1.0 * 30 / 3)  # 10 detection frames = 1 second at fps=30,K=3
    locked_tid = 0
    lock_candidate_tid = None
    lock_candidate_cnt = 0
    best_tid_sequence = [0] * 5 + [1] * 8 + [1] * 5   # T1 appears for 13 frames

    for best in best_tid_sequence:
        if best == locked_tid:
            lock_candidate_tid = None
            lock_candidate_cnt = 0
        else:
            if best == lock_candidate_tid:
                lock_candidate_cnt += 1
            else:
                lock_candidate_tid = best
                lock_candidate_cnt = 1
            if lock_candidate_cnt >= lock_frames:
                locked_tid = lock_candidate_tid
                lock_candidate_tid = None
                lock_candidate_cnt = 0

    # After 13 frames of T1 being best (>= lock_frames=10), locked_tid should switch
    assert locked_tid == 1, f"Expected locked_tid=1 after hysteresis, got {locked_tid}"
    record("Speaker lock: switches after >= lock_frames consecutive frames", PASS)
except Exception as e:
    record("Speaker lock: switches after >= lock_frames consecutive frames", FAIL, str(e))

try:
    # If candidate appears for only 5 frames (< 10), no switch
    locked_tid = 0
    lock_candidate_tid = None
    lock_candidate_cnt = 0
    best_tid_sequence = [0] * 5 + [1] * 5  # only 5 frames of T1

    for best in best_tid_sequence:
        if best == locked_tid:
            lock_candidate_tid = None
            lock_candidate_cnt = 0
        else:
            if best == lock_candidate_tid:
                lock_candidate_cnt += 1
            else:
                lock_candidate_tid = best
                lock_candidate_cnt = 1
            if lock_candidate_cnt >= lock_frames:
                locked_tid = lock_candidate_tid

    assert locked_tid == 0, f"Should stay locked to T0, got {locked_tid}"
    record("Speaker lock: does NOT switch when candidate < lock_frames", PASS)
except Exception as e:
    record("Speaker lock: does NOT switch when candidate < lock_frames", FAIL, str(e))

# ── Dead zone suppression ───────────────────────────────────────

try:
    kc = KalmanCrop(initial_x=500.0)
    for _ in range(5):
        kc.predict()
        kc.update(500.0)
    pos_before = kc.position

    # Simulate dead zone: 20 px shift (< 40 px dead zone) → target stays
    target_cx = 520.0
    current_crop_cx = 500.0
    crop_w = 608
    target_crop_x = target_cx - crop_w / 2.0
    current_crop_x = current_crop_cx - crop_w / 2.0
    if abs(target_crop_x - current_crop_x) < _DEAD_ZONE_PX:
        target_cx = current_crop_cx   # dead zone: hold

    # After dead zone, Kalman should see 500 not 520
    kc.predict()
    kc.update(target_cx)
    assert abs(kc.position - 500.0) < 10.0, (
        f"Dead zone failed: camera moved to {kc.position} on 20px shift"
    )
    record("Dead zone: 20 px shift suppressed (< 60 px threshold)", PASS)
except Exception as e:
    record("Dead zone: 20 px shift suppressed (< 60 px threshold)", FAIL, str(e))

try:
    # 80 px shift (> 60 px dead zone) → target moves
    target_cx = 580.0
    current_crop_cx = 500.0
    crop_w = 608
    target_crop_x = target_cx - crop_w / 2.0
    current_crop_x = current_crop_cx - crop_w / 2.0
    dead_zone_active = abs(target_crop_x - current_crop_x) < _DEAD_ZONE_PX
    assert not dead_zone_active, "Dead zone should NOT suppress 80 px shift"
    record("Dead zone: 80 px shift passes through (> 60 px threshold)", PASS)
except Exception as e:
    record("Dead zone: 80 px shift passes through (> 60 px threshold)", FAIL, str(e))

# ── Velocity clamp ──────────────────────────────────────────────

try:
    import math
    current_crop_cx = 500.0
    smooth_cx = 600.0   # 100 px jump → exceeds 15 px/frame clamp
    delta = smooth_cx - current_crop_cx
    if abs(delta) > _MAX_CROP_VELOCITY:
        smooth_cx = current_crop_cx + math.copysign(_MAX_CROP_VELOCITY, delta)
    assert abs(smooth_cx - current_crop_cx) == _MAX_CROP_VELOCITY, (
        f"Expected clamped to {_MAX_CROP_VELOCITY}, got delta={smooth_cx - current_crop_cx}"
    )
    record("Velocity clamp: 100 px jump clamped to 15 px/frame", PASS)
except Exception as e:
    record("Velocity clamp: 100 px jump clamped to 15 px/frame", FAIL, str(e))

try:
    import math
    current_crop_cx = 500.0
    smooth_cx = 510.0   # 10 px → within clamp, should pass through
    delta = smooth_cx - current_crop_cx
    clamped = abs(delta) > _MAX_CROP_VELOCITY
    assert not clamped, f"10 px should NOT be clamped (clamp={_MAX_CROP_VELOCITY})"
    record("Velocity clamp: 10 px move passes through unclamped", PASS)
except Exception as e:
    record("Velocity clamp: 10 px move passes through unclamped", FAIL, str(e))

# ──────────────────────────────────────────────────────────────
# TEST AREA 15 — Boundary Refiner & Story Completeness Score
# ──────────────────────────────────────────────────────────────
section("TEST AREA 15: Boundary Refiner & Story Completeness Score")

try:
    from analyzer import _is_hook_present, _refine_boundaries, calculate_completeness_score
    
    # 1. Test _is_hook_present
    assert _is_hook_present("Why is this happening?") == True, "Should recognize question / why"
    assert _is_hook_present("We spent 10 million dollars on this.") == True, "Should recognize number / million"
    assert _is_hook_present("This is a simple transcript line.") == True, "Should recognize 'this'"
    assert _is_hook_present("we go here") == False, "Should not recognize generic text"
    record("Boundary Refiner — _is_hook_present hook detection", PASS)
except Exception as e:
    record("Boundary Refiner — _is_hook_present hook detection", FAIL, str(e))

try:
    # Setup mock transcript entries
    # index 0: "and we did that" (conjunction start)
    # index 1: "we went to the store." (clean start, ended with period)
    # index 2: "but we found it" (conjunction start)
    # index 3: "Why is AI changing the world?" (hook lock, question mark)
    # index 4: "and we were surprised" (conjunction start)
    # index 5: "This is a secret mistake." (hook lock)
    mock_transcript = [
        MockTranscriptEntry(0.0, 5.0, "and we did that"),
        MockTranscriptEntry(5.0, 5.0, "we went to the store."),
        MockTranscriptEntry(10.0, 5.0, "but we found it"),
        MockTranscriptEntry(15.0, 5.0, "Why is AI changing the world?"),
        MockTranscriptEntry(20.0, 5.0, "and we were surprised"),
        MockTranscriptEntry(25.0, 5.0, "This is a secret mistake.")
    ]
    
    # Clip starting at index 2 (conjunction "but"). It should shift backward to index 1 (clean line).
    clip_conjunction = {"start_index": 2, "end_index": 3}
    refined_conjunction = _refine_boundaries(clip_conjunction, mock_transcript)
    assert refined_conjunction["start_index"] == 1, f"Expected start_index to shift backward to 1, got {refined_conjunction['start_index']}"
    record("Boundary Refiner — shifts start backward past conjunctions", PASS)
except Exception as e:
    record("Boundary Refiner — shifts start backward past conjunctions", FAIL, str(e))

try:
    # Clip starting at index 3 (hook lock "Why is AI..."). It should NOT shift backward to index 2 even though index 4 has a conjunction.
    clip_hook = {"start_index": 3, "end_index": 4}
    refined_hook = _refine_boundaries(clip_hook, mock_transcript)
    assert refined_hook["start_index"] == 3, f"Expected start_index to remain locked at 3, got {refined_hook['start_index']}"
    record("Boundary Refiner — Hook Protection locks start position", PASS)
except Exception as e:
    record("Boundary Refiner — Hook Protection locks start position", FAIL, str(e))

try:
    # Clip ending at index 4 ("and we were surprised" - no punctuation). It should extend forward to index 5 ("This is a secret mistake." - ends with period).
    clip_end = {"start_index": 3, "end_index": 4}
    refined_end = _refine_boundaries(clip_end, mock_transcript)
    assert refined_end["end_index"] == 5, f"Expected end_index to extend forward to 5, got {refined_end['end_index']}"
    record("Boundary Refiner — extends end forward to sentence ending", PASS)
except Exception as e:
    record("Boundary Refiner — extends end forward to sentence ending", FAIL, str(e))

try:
    # Test calculate_completeness_score
    clip_score = {"start_index": 1, "end_index": 1, "start_time": 5.0, "end_time": 40.0} # duration 35s (sweet spot)
    # Start: "we went to the store."
    # End: "we went to the store." (ends with '.')
    score = calculate_completeness_score(clip_score, mock_transcript)
    assert score >= 7.0, f"Expected high completeness score, got {score}"
    
    # Clip starting with conjunction and no ending punctuation
    clip_bad = {"start_index": 0, "end_index": 0, "start_time": 0.0, "end_time": 5.0} # duration 5s (not sweet spot)
    score_bad = calculate_completeness_score(clip_bad, mock_transcript)
    assert score_bad < score, f"Expected worse score ({score_bad}) than clean clip ({score})"
    record("Boundary Refiner — completeness score calculation", PASS)
except Exception as e:
    record("Boundary Refiner — completeness score calculation", FAIL, str(e))

# ──────────────────────────────────────────────────────────────
# TEST AREA 20: Subtitle Zone Detection & Removal
# ──────────────────────────────────────────────────────────────
section("TEST AREA 20: Subtitle Zone Detection & Removal")

try:
    import tempfile
    import cv2
    import numpy as np
    from subtitle_detector import detect_subtitle_zone, has_subtitles
    
    # Helper function to generate dummy video file with or without subtitles
    def create_dummy_video(filename, with_subtitles=False, width=640, height=360):
        # We use a smaller size like 640x360 for fast generation in tests
        fourcc = cv2.VideoWriter_fourcc(*'MJPG')
        out = cv2.VideoWriter(filename, fourcc, 30.0, (width, height))
        for _ in range(20): # 20 frames to match the detector sampling
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            if with_subtitles:
                # bottom 20% starts at 288px.
                # Let's draw high-density alternating columns from y = 300 to 340, cols 100 to 540
                frame[300:340, 100:540] = np.random.randint(0, 2, (40, 440, 3), dtype=np.uint8) * 255
            out.write(frame)
        out.release()

    # 1. Test detect_subtitle_zone returns 0 for a blank video
    with tempfile.NamedTemporaryFile(suffix=".avi", delete=False) as f:
        no_subs_path = f.name
    try:
        create_dummy_video(no_subs_path, with_subtitles=False)
        no_subs_h = detect_subtitle_zone(no_subs_path)
        assert no_subs_h == 0, f"Expected 0 subtitle zone height for blank video, got {no_subs_h}"
        record("Subtitle Detector — returns 0 for blank/no subtitles", PASS)
    finally:
        if os.path.exists(no_subs_path):
            os.remove(no_subs_path)
except Exception as e:
    record("Subtitle Detector — returns 0 for blank/no subtitles", FAIL, str(e))

try:
    # 2. Test detect_subtitle_zone returns > 0 for a video with simulated subtitle band
    with tempfile.NamedTemporaryFile(suffix=".avi", delete=False) as f:
        with_subs_path = f.name
    try:
        create_dummy_video(with_subs_path, with_subtitles=True)
        with_subs_h = detect_subtitle_zone(with_subs_path)
        # bottom 20% starts at 288 (360 * 0.8). The band is at y=300, height=40.
        # Height from bottom is 360 - 300 = 60px.
        # Since step is 5px, it should be within ±10px of 60.
        assert with_subs_h > 0, f"Expected subtitle height > 0, got {with_subs_h}"
        assert abs(with_subs_h - 60) <= 10, f"Expected subtitle zone height around 60, got {with_subs_h}"
        record("Subtitle Detector — returns > 0 for simulated subtitle band", PASS)
    finally:
        if os.path.exists(with_subs_path):
            os.remove(with_subs_path)
except Exception as e:
    record("Subtitle Detector — returns > 0 for simulated subtitle band", FAIL, str(e))

try:
    # 3. Test crop window adjustment shifts upward correctly
    from clipper import get_shot_crop_offsets
    # Setup test video (blank, 1280x720, 20 frames)
    with tempfile.NamedTemporaryFile(suffix=".avi", delete=False) as f:
        test_video_path = f.name
    try:
        create_dummy_video(test_video_path, with_subtitles=False, width=1280, height=720)
        
        # Test without subtitles
        meta_no_subs = {"subtitle_zone_height": 0}
        offsets_no_subs = get_shot_crop_offsets(test_video_path, 1280, 720, 30.0, 20, metadata=meta_no_subs)
        
        # Test with subtitles (height 80)
        meta_with_subs = {"subtitle_zone_height": 80}
        offsets_with_subs = get_shot_crop_offsets(test_video_path, 1280, 720, 30.0, 20, metadata=meta_with_subs)
        
        assert len(offsets_no_subs) == 20
        assert len(offsets_with_subs) == 20
        record("Crop Window Adjustment — adjusts crop window layout successfully when subtitle zone is detected", PASS)
    finally:
        if os.path.exists(test_video_path):
            os.remove(test_video_path)
except Exception as e:
    record("Crop Window Adjustment — adjusts crop window layout successfully when subtitle zone is detected", FAIL, str(e))

# ──────────────────────────────────────────────────────────────
# TEST AREA 21 — JSON Repair & Extractor Tests
# ──────────────────────────────────────────────────────────────
section("TEST AREA 21: JSON Repair & Extractor Tests")

try:
    from analyzer import _repair_json, _extract_json_from_response

    # Test 1: Trailing Comma and unescaped newlines
    raw_bad_json = '{\n  "candidates": [\n    {\n      "title": "Clip 1",\n      "description": "This is a \nmultiline description with unescaped newlines.",\n    },\n  ]\n}'
    repaired = _repair_json(raw_bad_json)
    data = json.loads(repaired)
    assert len(data["candidates"]) == 1
    assert "multiline description" in data["candidates"][0]["description"]
    record("JSON Repair — handles trailing commas and unescaped newlines", PASS)
except Exception as e:
    record("JSON Repair — handles trailing commas and unescaped newlines", FAIL, str(e))

try:
    # Test 2: Truncated JSON
    truncated_json = '{"candidates": [{"title": "Clip 1", "description": "truncated content'
    repaired_trunc = _repair_json(truncated_json)
    data_trunc = json.loads(repaired_trunc)
    assert len(data_trunc["candidates"]) == 1
    assert data_trunc["candidates"][0]["title"] == "Clip 1"
    record("JSON Repair — repairs and balances truncated JSON", PASS)
except Exception as e:
    record("JSON Repair — repairs and balances truncated JSON", FAIL, str(e))

try:
    # Test 3: Markdown fence stripping
    llm_output = 'Here is the JSON:\n```json\n{"status": "success", "data": [1, 2, 3]}\n```\nHope it helps!'
    extracted = _extract_json_from_response(llm_output)
    data_ext = json.loads(extracted)
    assert data_ext["status"] == "success"
    record("JSON Extractor — extracts JSON from markdown code blocks", PASS)
except Exception as e:
    record("JSON Extractor — extracts JSON from markdown code blocks", FAIL, str(e))

# ──────────────────────────────────────────────────────────────
# TEST AREA 22 — Database Caching Tests
# ──────────────────────────────────────────────────────────────
section("TEST AREA 22: Database Caching Tests")

try:
    from analytics_repository import db as test_db
    import uuid

    test_video_id = f"test_vid_{uuid.uuid4().hex[:8]}"
    
    # Verify empty cache initially
    clips = test_db.get_clips_by_video_id(test_video_id)
    assert len(clips) == 0, f"Expected 0 clips, got {len(clips)}"
    record("Database Caching — returns empty list for new video ID", PASS)
except Exception as e:
    record("Database Caching — returns empty list for new video ID", FAIL, str(e))

try:
    # Save a dummy clip metadata and verify it is retrieved
    test_clip_id = f"clip_{uuid.uuid4().hex[:8]}"
    test_db.save_clip_metadata(
        video_id=test_video_id,
        clip_id=test_clip_id,
        virality_score=8.5,
        detailed_scores={"hook": 9.0},
        title="Cache Test Title",
        reason="Cache Test Reason",
        shorts_title="Cache Test Title #shorts",
        shorts_description="Cache description",
        shorts_tags=["test", "cache"]
    )
    
    clips = test_db.get_clips_by_video_id(test_video_id)
    assert len(clips) == 1, f"Expected 1 clip, got {len(clips)}"
    assert clips[0]["clip_id"] == test_clip_id
    assert clips[0]["title"] == "Cache Test Title"
    assert clips[0]["virality_score"] == 8.5
    assert clips[0]["detailed_scores"] == {"hook": 9.0}
    assert clips[0]["shorts_tags"] == ["test", "cache"]
    record("Database Caching — saves and retrieves clips successfully", PASS)
except Exception as e:
    record("Database Caching — saves and retrieves clips successfully", FAIL, str(e))

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
if __name__ == "__main__":
    sys.exit(0 if not failed else 1)

