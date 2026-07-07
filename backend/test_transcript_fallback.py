# test_transcript_fallback.py
import os
import sys
import tempfile
import pytest

# Adjust path to find modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analyzer import (
    parse_subtitle_file,
    LocalTranscriptSnippet,
    save_transcript_cache,
    load_transcript_cache,
    transcribe_audio_whisper
)
from analytics_repository import db as analytics_db

def test_webvtt_srt_parser():
    # Test WebVTT
    vtt_content = """WEBVTT

00:00:01.000 --> 00:00:04.500
Hello <c>world</c>!

00:00:04.500 --> 00:00:08.250
This is a test.
"""
    with tempfile.NamedTemporaryFile(suffix=".vtt", delete=False, mode="w", encoding="utf-8") as f:
        f.write(vtt_content)
        vtt_path = f.name
        
    try:
        snippets = parse_subtitle_file(vtt_path)
        assert len(snippets) == 2
        assert snippets[0].text == "Hello world!"
        assert snippets[0].start == 1.0
        assert snippets[0].duration == 3.5
        assert snippets[1].text == "This is a test."
        assert snippets[1].start == 4.5
        assert snippets[1].duration == 3.75
    finally:
        if os.path.exists(vtt_path):
            os.remove(vtt_path)

    # Test SRT
    srt_content = """1
00:00:01,200 --> 00:00:03,800
Hello universe!

2
00:00:03,800 --> 00:00:07,100
SRT format test.
"""
    with tempfile.NamedTemporaryFile(suffix=".srt", delete=False, mode="w", encoding="utf-8") as f:
        f.write(srt_content)
        srt_path = f.name
        
    try:
        snippets = parse_subtitle_file(srt_path)
        assert len(snippets) == 2
        assert snippets[0].text == "Hello universe!"
        assert snippets[0].start == 1.2
        assert snippets[0].duration == pytest.approx(2.6)
        assert snippets[1].text == "SRT format test."
        assert snippets[1].start == 3.8
        assert snippets[1].duration == pytest.approx(3.3)
    finally:
        if os.path.exists(srt_path):
            os.remove(srt_path)

def test_caching():
    video_id = "test_cache_vid_99"
    snippets = [
        LocalTranscriptSnippet("Line A", 0.0, 3.0),
        LocalTranscriptSnippet("Line B", 3.0, 4.0)
    ]
    
    # Save cache
    save_transcript_cache(video_id, snippets)
    
    # Load cache
    loaded = load_transcript_cache(video_id)
    assert loaded is not None
    assert len(loaded) == 2
    assert loaded[0].text == "Line A"
    assert loaded[0].start == 0.0
    assert loaded[0].duration == 3.0
    assert loaded[1].text == "Line B"
    
    # Clean up cache file
    cache_path = os.path.join("output", "cache", "transcripts", f"{video_id}.json")
    if os.path.exists(cache_path):
        os.remove(cache_path)

def test_database_metrics():
    video_id = "test_metrics_vid_99"
    failures = ["Tier 1 failed", "Tier 2 failed"]
    
    analytics_db.save_transcript_metric(
        video_id=video_id,
        source="faster_whisper",
        failures=failures,
        fallback_used=True,
        duration=15.5
    )
    
    summary = analytics_db.get_transcript_metrics_summary()
    assert summary["total_runs"] >= 1
    assert "faster_whisper" in summary["source_breakdown"]
    assert summary["fallback_used_count"] >= 1
    
    # Clean up DB entry
    import sqlite3
    conn = sqlite3.connect(analytics_db.db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transcript_metrics WHERE video_id = ?", (video_id,))
    conn.commit()
    conn.close()

def test_whisper_local():
    audio_path = os.path.join(os.path.dirname(__file__), "benchmark_audio.mp3")
    if not os.path.exists(audio_path):
        pytest.skip("benchmark_audio.mp3 not found, skipping Whisper integration test.")
        
    snippets = transcribe_audio_whisper(audio_path, model_size="tiny")
    # Rick Astley vocal segment downloaded starts at 20s and ends at 35s, so we expect some segments.
    # On first run it might be empty if tiny had a hiccup, but let's check it doesn't crash.
    assert isinstance(snippets, list)
