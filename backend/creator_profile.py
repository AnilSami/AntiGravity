"""
creator_profile.py — Analyzes historical clip metadata to build a creator style profile.

Computes distributions for subtitle styles, energy, emotions, duration,
words per chunk, and reading speeds to personalize future generation.
"""

import logging
import collections
import time
from typing import Optional
from analytics_repository import db as analytics_db

logger = logging.getLogger("creator_profile")

DEFAULT_PROFILE_VERSION = "default"

# Fallback profile constants
DEFAULT_STYLE_PREFERENCES = {
    "subtitle_style": "kinetic",
    "clip_duration_secs": 42.0,
    "reading_speed_wpm": 180.0,
    "words_per_chunk": 2.5,
    "energy_level": 7,
    "primary_emotion": "engaging",
    "creator_preset": "custom",
    "sample_count": 0
}

DEFAULT_VIRALITY_WEIGHTS = {
    "hook_weight": 0.35,
    "retention_weight": 0.25,
    "density_weight": 0.20,
    "flow_weight": 0.20
}


def compile_creator_profile() -> dict:
    """
    Scans the local SQLite database for all clip metadata and feedback
    to extract average stylistic preferences and performance trends.
    """
    try:
        records = analytics_db.get_all_records()
    except Exception as e:
        logger.error(f"Failed to fetch database records: {e}")
        records = []

    if not records:
        logger.info("No clips found in database. Using default style configuration.")
        return {
            "style_preferences": DEFAULT_STYLE_PREFERENCES.copy(),
            "performance_rules": {
                "best_post_hours": [12, 17, 20],
                "top_performing_presets": ["custom"]
            }
        }

    # Extract styling metadata from clips that were "selected" by the creator,
    # "published" to platforms, or have positive feedback, to capture preferred styles.
    preferred_clips = []
    for r in records:
        is_preferred = (
            r.get("creator_selected") == 1
            or r.get("published") == 1
            or (r.get("feedback") and "good" in r.get("feedback").lower())
        )
        if is_preferred:
            preferred_clips.append(r)

    # If no explicitly preferred clips exist, analyze all clips as baseline
    source_clips = preferred_clips if preferred_clips else records

    # Initialize aggregators
    subtitle_styles = []
    emotions = []
    presets = []
    durations = []
    speeds = []
    chunks = []
    energies = []

    for c in source_clips:
        if c.get("subtitle_style"):
            subtitle_styles.append(c["subtitle_style"])
        if c.get("emotion"):
            emotions.append(c["emotion"])
        if c.get("creator_preset"):
            presets.append(c["creator_preset"])
        if c.get("duration") and c["duration"] > 0:
            durations.append(c["duration"])
        if c.get("reading_speed") and c["reading_speed"] > 0:
            speeds.append(c["reading_speed"])
        if c.get("words_per_chunk") and c["words_per_chunk"] > 0:
            chunks.append(c["words_per_chunk"])
        if c.get("energy_level") and c["energy_level"] > 0:
            energies.append(c["energy_level"])

    # Calculate style preference metrics (modes or averages)
    def mode(lst, default):
        if not lst:
            return default
        return collections.Counter(lst).most_common(1)[0][0]

    pref_style = mode(subtitle_styles, DEFAULT_STYLE_PREFERENCES["subtitle_style"])
    pref_emotion = mode(emotions, DEFAULT_STYLE_PREFERENCES["primary_emotion"])
    pref_preset = mode(presets, DEFAULT_STYLE_PREFERENCES["creator_preset"])

    avg_duration = sum(durations) / len(durations) if durations else DEFAULT_STYLE_PREFERENCES["clip_duration_secs"]
    avg_speed = sum(speeds) / len(speeds) if speeds else DEFAULT_STYLE_PREFERENCES["reading_speed_wpm"]
    avg_chunk = sum(chunks) / len(chunks) if chunks else DEFAULT_STYLE_PREFERENCES["words_per_chunk"]
    avg_energy = sum(energies) / len(energies) if energies else DEFAULT_STYLE_PREFERENCES["energy_level"]

    style_prefs = {
        "subtitle_style": pref_style,
        "clip_duration_secs": round(avg_duration, 1),
        "reading_speed_wpm": round(avg_speed, 1),
        "words_per_chunk": round(avg_chunk, 2),
        "energy_level": int(round(avg_energy)),
        "primary_emotion": pref_emotion,
        "creator_preset": pref_preset,
        "sample_count": len(source_clips)
    }

    # Extract performance trends
    best_hours = []
    # YouTube Analytics snapshots analysis (if platform performance is populated)
    # Simple extraction of best posting times based on snapshot data
    for r in records:
        if r.get("views") and r["views"] > 100:
            # Placeholder or actual logic depending on snapshot timestamp hours
            pass

    return {
        "style_preferences": style_prefs,
        "performance_rules": {
            "best_post_hours": best_hours if best_hours else [12, 17, 20],
            "top_performing_presets": [pref_preset] if pref_preset else ["custom"]
        }
    }


def get_creator_profile(profile_version: str = DEFAULT_PROFILE_VERSION) -> dict:
    """
    Retrieves the creator's profile state from the database.
    If it doesn't exist, builds it for the first time and saves it.
    """
    state = analytics_db.get_creator_profile_state(profile_version)
    if not state:
        logger.info(f"Creator profile '{profile_version}' not found. Compiling first profile...")
        profile = compile_creator_profile()
        analytics_db.save_creator_profile_state(
            profile_version=profile_version,
            style_preferences=profile["style_preferences"],
            virality_weights=DEFAULT_VIRALITY_WEIGHTS.copy()
        )
        return {
            "profile_version": profile_version,
            "style_preferences": profile["style_preferences"],
            "virality_weights": DEFAULT_VIRALITY_WEIGHTS.copy(),
            "last_updated": time.time()
        }
    return state


def rebuild_creator_profile(profile_version: str = DEFAULT_PROFILE_VERSION) -> dict:
    """
    Forces recalculation of creator style profile and saves it.
    """
    logger.info(f"Rebuilding creator profile '{profile_version}'...")
    profile = compile_creator_profile()
    # Retain existing virality weights if present
    existing = analytics_db.get_creator_profile_state(profile_version)
    weights = existing["virality_weights"] if existing and existing.get("virality_weights") else DEFAULT_VIRALITY_WEIGHTS.copy()

    analytics_db.save_creator_profile_state(
        profile_version=profile_version,
        style_preferences=profile["style_preferences"],
        virality_weights=weights
    )
    return {
        "profile_version": profile_version,
        "style_preferences": profile["style_preferences"],
        "virality_weights": weights
    }
