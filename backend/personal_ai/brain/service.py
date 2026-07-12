"""
service.py — Manages Creator Profile, Editing Preferences, and Long-Term Goals.
"""

import json
import time
import logging
from typing import Optional
from analytics_repository import db as analytics_db
from personal_ai.models.schemas import (
    CreatorBrainModel, CreatorProfileModel, CreatorGoalsModel,
    CreatorPreferencesModel, StylePreferencesModel, EditingPreferencesModel,
    MusicPreferencesModel, PublishingScheduleModel
)

logger = logging.getLogger("personal_ai.brain.service")


def get_creator_brain(brain_id: str = "default") -> CreatorBrainModel:
    """Retrieves creator brain state from the SQLite database."""
    conn = analytics_db._get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM creator_brain WHERE brain_id = ?", (brain_id,))
        row = cursor.fetchone()
        if not row:
            # Seed default brain state
            profile = CreatorProfileModel(
                niche="tech",
                tone="engaging",
                demographics={"18-24": 0.40, "25-34": 0.50},
                geographic_focus=["US", "GB", "IN"]
            )
            goals = CreatorGoalsModel(
                primary_metric="retention",
                subscriber_target=10000,
                niche_focus=["coding", "ai", "productivity"]
            )
            default_brain = CreatorBrainModel(
                brain_id=brain_id,
                creator_profile=profile,
                audience_profile={"returning_viewers_pct": 0.35},
                goals=goals,
                updated_at=time.time()
            )
            save_creator_brain(default_brain)
            return default_brain

        # Parse DB row
        # Row layout: brain_id, creator_profile, audience_profile, goals, updated_at
        brain_data = dict(zip([col[0] for col in cursor.description], row))
        return CreatorBrainModel(
            brain_id=brain_data["brain_id"],
            creator_profile=CreatorProfileModel(**json.loads(brain_data["creator_profile"])),
            audience_profile=json.loads(brain_data["audience_profile"]),
            goals=CreatorGoalsModel(**json.loads(brain_data["goals"])),
            updated_at=brain_data["updated_at"]
        )
    finally:
        conn.close()


def save_creator_brain(brain: CreatorBrainModel):
    """Saves creator brain state to the SQLite database."""
    conn = analytics_db._get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO creator_brain (brain_id, creator_profile, audience_profile, goals, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(brain_id) DO UPDATE SET
                    creator_profile = excluded.creator_profile,
                    audience_profile = excluded.audience_profile,
                    goals = excluded.goals,
                    updated_at = excluded.updated_at
            """, (
                brain.brain_id,
                brain.creator_profile.model_dump_json(),
                json.dumps(brain.audience_profile),
                brain.goals.model_dump_json(),
                time.time()
            ))
    finally:
        conn.close()


def get_creator_preferences(pref_id: str = "default") -> CreatorPreferencesModel:
    """Retrieves creator style and editing preferences from the SQLite database."""
    conn = analytics_db._get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM creator_preferences WHERE pref_id = ?", (pref_id,))
        row = cursor.fetchone()
        if not row:
            # Seed default preferences
            default_prefs = CreatorPreferencesModel(
                pref_id=pref_id,
                style_prefs=StylePreferencesModel(),
                editing_prefs=EditingPreferencesModel(),
                music_prefs=MusicPreferencesModel(),
                publishing_schedule=PublishingScheduleModel(),
                updated_at=time.time()
            )
            save_creator_preferences(default_prefs)
            return default_prefs

        pref_data = dict(zip([col[0] for col in cursor.description], row))
        return CreatorPreferencesModel(
            pref_id=pref_data["pref_id"],
            style_prefs=StylePreferencesModel(**json.loads(pref_data["style_prefs"])),
            editing_prefs=EditingPreferencesModel(**json.loads(pref_data["editing_prefs"])),
            music_prefs=MusicPreferencesModel(**json.loads(pref_data["music_prefs"])),
            publishing_schedule=PublishingScheduleModel(**json.loads(pref_data["publishing_schedule"])),
            updated_at=pref_data["updated_at"]
        )
    finally:
        conn.close()


def save_creator_preferences(prefs: CreatorPreferencesModel):
    """Saves creator preferences to the SQLite database."""
    conn = analytics_db._get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO creator_preferences (pref_id, style_prefs, editing_prefs, music_prefs, publishing_schedule, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(pref_id) DO UPDATE SET
                    style_prefs = excluded.style_prefs,
                    editing_prefs = excluded.editing_prefs,
                    music_prefs = excluded.music_prefs,
                    publishing_schedule = excluded.publishing_schedule,
                    updated_at = excluded.updated_at
            """, (
                prefs.pref_id,
                prefs.style_prefs.model_dump_json(),
                prefs.editing_prefs.model_dump_json(),
                prefs.music_prefs.model_dump_json(),
                prefs.publishing_schedule.model_dump_json(),
                time.time()
            ))
    finally:
        conn.close()
