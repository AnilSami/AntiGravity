"""
Unit tests for the Creator Profile Engine (creator_profile.py).
"""

import pytest
import shutil
import tempfile
import os
from analytics_repository import SqliteAnalyticsRepository
import creator_profile

@pytest.fixture
def temp_db():
    """Create a temporary sqlite database for testing."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_analytics.db")
    
    # Instantiate clean repository
    repo = SqliteAnalyticsRepository(db_path=db_path)
    
    # Save original db instance and swap it
    original_db = creator_profile.analytics_db
    creator_profile.analytics_db = repo
    
    yield repo
    
    # Restore original db instance and clean directory
    creator_profile.analytics_db = original_db
    shutil.rmtree(temp_dir)


def test_compile_profile_empty_db(temp_db):
    """Verify profile compilation handles empty database by returning defaults."""
    profile = creator_profile.compile_creator_profile()
    assert profile["style_preferences"]["subtitle_style"] == "kinetic"
    assert profile["style_preferences"]["energy_level"] == 7
    assert profile["style_preferences"]["sample_count"] == 0


def test_compile_profile_with_records(temp_db):
    """Verify profile aggregates records correctly to find preferences."""
    # Seed mock records
    # clip 1: classic, 30s, 150 wpm, energy 5, emotion: happy, selected=1
    temp_db.save_clip_metadata(
        video_id="vid1",
        clip_id="clip1",
        virality_score=8.5,
        detailed_scores={},
        subtitle_style="classic",
        duration=30.0,
        reading_speed=150.0,
        words_per_chunk=2.0,
        creator_preset="presetA",
        emotion="happy",
        energy_level=5
    )
    temp_db.update_creator_action("clip1", selected=True)

    # clip 2: classic, 40s, 160 wpm, energy 6, emotion: happy, selected=1
    temp_db.save_clip_metadata(
        video_id="vid1",
        clip_id="clip2",
        virality_score=9.0,
        detailed_scores={},
        subtitle_style="classic",
        duration=40.0,
        reading_speed=160.0,
        words_per_chunk=3.0,
        creator_preset="presetA",
        emotion="happy",
        energy_level=6
    )
    temp_db.update_creator_action("clip2", selected=True)

    # clip 3: kinetic, 50s, 220 wpm, energy 9, emotion: excited, selected=0 (rejected)
    temp_db.save_clip_metadata(
        video_id="vid1",
        clip_id="clip3",
        virality_score=7.0,
        detailed_scores={},
        subtitle_style="kinetic",
        duration=50.0,
        reading_speed=220.0,
        words_per_chunk=4.0,
        creator_preset="presetB",
        emotion="excited",
        energy_level=9
    )
    temp_db.update_creator_action("clip3", rejected=True)

    # Compile profile
    profile = creator_profile.compile_creator_profile()
    prefs = profile["style_preferences"]

    # Since we have explicitly "selected" clips, it should bias preferences toward them (clips 1 and 2)
    assert prefs["subtitle_style"] == "classic"
    assert prefs["primary_emotion"] == "happy"
    assert prefs["creator_preset"] == "presetA"
    assert prefs["clip_duration_secs"] == 35.0  # (30 + 40) / 2
    assert prefs["reading_speed_wpm"] == 155.0  # (150 + 160) / 2
    assert prefs["words_per_chunk"] == 2.5      # (2.0 + 3.0) / 2
    assert prefs["energy_level"] == 6           # round((5 + 6)/2)
    assert prefs["sample_count"] == 2           # Only count the 2 preferred clips since we filtered by preference


def test_get_and_rebuild_state(temp_db):
    """Verify profile state is saved and read from sqlite correctly."""
    # First get should compile and save defaults
    state = creator_profile.get_creator_profile("test_ver")
    assert state["profile_version"] == "test_ver"
    assert state["style_preferences"]["subtitle_style"] == "kinetic"

    # Seed a clip to database
    temp_db.save_clip_metadata(
        video_id="vid1",
        clip_id="c1",
        virality_score=9.5,
        detailed_scores={},
        subtitle_style="karaoke"
    )
    temp_db.update_creator_action("c1", selected=True)

    # Rebuild should update the saved profile state
    new_state = creator_profile.rebuild_creator_profile("test_ver")
    assert new_state["style_preferences"]["subtitle_style"] == "karaoke"
    assert new_state["style_preferences"]["sample_count"] == 1

    # Next get should return the updated karaoke preference from DB
    loaded = creator_profile.get_creator_profile("test_ver")
    assert loaded["style_preferences"]["subtitle_style"] == "karaoke"
