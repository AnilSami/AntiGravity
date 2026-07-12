"""
Unit tests for personal_ai/brain/service.py
"""

import pytest
import shutil
import tempfile
import os
import time
from analytics_repository import SqliteAnalyticsRepository
import personal_ai.brain.service as brain_service
from personal_ai.models.schemas import CreatorBrainModel, CreatorProfileModel, CreatorGoalsModel

@pytest.fixture
def temp_db():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_personal.db")
    repo = SqliteAnalyticsRepository(db_path=db_path)
    
    # Temporarily swap global database dependency in brain_service
    original_db = brain_service.analytics_db
    brain_service.analytics_db = repo
    
    yield repo
    
    brain_service.analytics_db = original_db
    shutil.rmtree(temp_dir)


def test_get_creator_brain_defaults(temp_db):
    """Verify get_creator_brain initializes default profile values if table is empty."""
    brain = brain_service.get_creator_brain("test_brain")
    assert brain.brain_id == "test_brain"
    assert brain.creator_profile.niche == "tech"
    assert brain.goals.primary_metric == "retention"


def test_save_and_retrieve_brain(temp_db):
    """Verify saved creator_brain properties are persisted and loaded correctly."""
    profile = CreatorProfileModel(
        niche="education",
        tone="calm",
        demographics={"25-34": 0.8},
        geographic_focus=["CA"]
    )
    goals = CreatorGoalsModel(
        primary_metric="views",
        subscriber_target=50000,
        niche_focus=["tutorial", "python"]
    )
    brain = CreatorBrainModel(
        brain_id="my_custom_brain",
        creator_profile=profile,
        audience_profile={"new_audience_pct": 0.65},
        goals=goals,
        updated_at=time.time()
    )
    
    brain_service.save_creator_brain(brain)
    
    loaded = brain_service.get_creator_brain("my_custom_brain")
    assert loaded.creator_profile.niche == "education"
    assert loaded.creator_profile.tone == "calm"
    assert loaded.goals.subscriber_target == 50000
    assert loaded.audience_profile.get("new_audience_pct") == 0.65
