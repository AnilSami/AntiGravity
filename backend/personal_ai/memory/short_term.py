"""
short_term.py — Manages short-term/active session caches.
"""

from typing import Dict, Any, Optional

# Global in-memory cache to store active generation session states
_SESSION_CACHE: Dict[str, Dict[str, Any]] = {}


def start_session(video_id: str, transcript: list) -> Dict[str, Any]:
    """Starts a new generation session cached in memory."""
    _SESSION_CACHE[video_id] = {
        "transcript": transcript,
        "proposed_strategies": [],
        "approved_clips": [],
        "active_parameters": {},
        "created_at": float
    }
    return _SESSION_CACHE[video_id]


def update_session(video_id: str, key: str, value: Any):
    """Updates an active session attribute."""
    if video_id not in _SESSION_CACHE:
        _SESSION_CACHE[video_id] = {}
    _SESSION_CACHE[video_id][key] = value


def get_session(video_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves session state for a video."""
    return _SESSION_CACHE.get(video_id)


def clear_session(video_id: str):
    """Removes video session state from cache."""
    if video_id in _SESSION_CACHE:
        del _SESSION_CACHE[video_id]
