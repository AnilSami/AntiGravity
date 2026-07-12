"""
Unit tests for the Learning Engine feedback loops (learning_engine.py).
"""

import pytest
import shutil
import tempfile
import os
from analytics_repository import SqliteAnalyticsRepository
import learning_engine
import creator_profile

@pytest.fixture
def temp_db():
    """Create a temporary sqlite database for testing."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_analytics.db")
    
    # Instantiate clean repository
    repo = SqliteAnalyticsRepository(db_path=db_path)
    
    # Swap instances
    original_db = learning_engine.analytics_db
    learning_engine.analytics_db = repo
    creator_profile.analytics_db = repo
    
    yield repo
    
    # Restore
    learning_engine.analytics_db = original_db
    creator_profile.analytics_db = original_db
    shutil.rmtree(temp_dir)


def test_adjust_weights_on_select(temp_db):
    """Verify selecting a clip with high hook score increases hook_weight."""
    # Seed profile first
    creator_profile.get_creator_profile("test_ver")

    # Seed a clip with high hook score (9.0) and low density (2.0)
    temp_db.save_clip_metadata(
        video_id="vid1",
        clip_id="c1",
        virality_score=8.0,
        detailed_scores={"hook": 9.0, "retention": 5.0, "density": 2.0, "flow": 4.0}
    )

    # Perform creator select action
    new_weights = learning_engine.adjust_weights_on_creator_action("c1", selected=True, rejected=False, profile_version="test_ver")
    
    # Hook weight should increase (default was 0.35)
    # Density weight should decrease (default was 0.20)
    assert new_weights["hook_weight"] > 0.35
    assert new_weights["density_weight"] < 0.20
    assert abs(sum(new_weights.values()) - 1.0) < 0.005  # Normalized to 1.0


def test_adjust_weights_on_reject(temp_db):
    """Verify rejecting a clip with high hook score decreases hook_weight."""
    creator_profile.get_creator_profile("test_ver")

    # Seed clip
    temp_db.save_clip_metadata(
        video_id="vid1",
        clip_id="c2",
        virality_score=8.0,
        detailed_scores={"hook": 9.0, "retention": 5.0, "density": 2.0, "flow": 4.0}
    )

    # Perform creator reject action
    new_weights = learning_engine.adjust_weights_on_creator_action("c2", selected=False, rejected=True, profile_version="test_ver")
    
    # Hook weight should decrease (since the creator rejected a high hook clip, meaning hook score was overvalued)
    assert new_weights["hook_weight"] < 0.35
    assert new_weights["density_weight"] > 0.20
    assert abs(sum(new_weights.values()) - 1.0) < 0.005  # Normalized to 1.0
