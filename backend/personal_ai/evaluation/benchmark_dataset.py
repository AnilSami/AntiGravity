"""
benchmark_dataset.py — Reproducible offline benchmark dataset of historical clips.
"""

from typing import Dict, List, Any

# Predefined historical clip dataset
HISTORICAL_CLIPS: List[Dict[str, Any]] = [
    {
        "clip_id": "hist_clip_001",
        "title": "Build an AI agent in 5 minutes! #shorts",
        "transcript": "We built a fully autonomous AI agent that commits code without human reviews. Stop writing manual code, let the agent do the work.",
        "predicted_score": 9.0,
        "actual_views": 15000,
        "retention": 0.85,
        "watch_time": 450.0,
        "CTR": 0.12,
        "likes": 950,
        "comments": 75,
        "shares": 120,
        "category": "viral"
    },
    {
        "clip_id": "hist_clip_002",
        "title": "Visual ffmpeg styling tutorial! #shorts",
        "transcript": "Today we look at visual ffmpeg filters. Learn to apply kinetic typography overlays and match audio waveforms.",
        "predicted_score": 8.0,
        "actual_views": 8500,
        "retention": 0.72,
        "watch_time": 255.0,
        "CTR": 0.09,
        "likes": 420,
        "comments": 30,
        "shares": 45,
        "category": "viral"
    },
    {
        "clip_id": "hist_clip_003",
        "title": "Database indexing syntax detail",
        "transcript": "In this technical tutorial, we analyze database indexing commands. Specifically CREATE INDEX CONCURRENTLY syntax on Postgres.",
        "predicted_score": 5.0,
        "actual_views": 1200,
        "retention": 0.40,
        "watch_time": 36.0,
        "CTR": 0.03,
        "likes": 25,
        "comments": 2,
        "shares": 1,
        "category": "underperforming"
    },
    {
        "clip_id": "hist_clip_004",
        "title": "Why manual code reviews fail",
        "transcript": "Stop doing manual code reviews in 2026. Here is why: they waste time, cause arguments, and miss obvious edge cases.",
        "predicted_score": 8.5,
        "actual_views": 12000,
        "retention": 0.81,
        "watch_time": 360.0,
        "CTR": 0.10,
        "likes": 780,
        "comments": 65,
        "shares": 95,
        "category": "viral"
    },
    {
        "clip_id": "hist_clip_005",
        "title": "Uvicorn worker options detailed",
        "transcript": "To scale FastAPI, configure Uvicorn worker class. Use gthread or uvicorn.workers.UvicornWorker for standard deployments.",
        "predicted_score": 5.5,
        "actual_views": 2500,
        "retention": 0.50,
        "watch_time": 75.0,
        "CTR": 0.05,
        "likes": 60,
        "comments": 8,
        "shares": 3,
        "category": "standard"
    },
    {
        "clip_id": "hist_clip_006",
        "title": "Write better git commits",
        "transcript": "Your git commit messages are terrible. Use imperative mood, keep the subject under 50 characters, and explain the why.",
        "predicted_score": 7.8,
        "actual_views": 7200,
        "retention": 0.70,
        "watch_time": 216.0,
        "CTR": 0.08,
        "likes": 390,
        "comments": 22,
        "shares": 35,
        "category": "viral"
    },
    {
        "clip_id": "hist_clip_007",
        "title": "FastAPI async vs def performance",
        "transcript": "Should you write async def or def in FastAPI endpoints? If calling blocking I/O without await, write def to run in threadpool.",
        "predicted_score": 7.5,
        "actual_views": 6100,
        "retention": 0.68,
        "watch_time": 183.0,
        "CTR": 0.07,
        "likes": 310,
        "comments": 15,
        "shares": 20,
        "category": "standard"
    },
    {
        "clip_id": "hist_clip_008",
        "title": "CRLF line ending configuration",
        "transcript": "How to handle LF and CRLF errors in Git. Run git config core.autocrlf true to automatically translate line endings.",
        "predicted_score": 4.5,
        "actual_views": 800,
        "retention": 0.35,
        "watch_time": 24.0,
        "CTR": 0.02,
        "likes": 12,
        "comments": 1,
        "shares": 0,
        "category": "underperforming"
    },
    {
        "clip_id": "hist_clip_009",
        "title": "Stop using JWTs for sessions",
        "transcript": "Stop using JWTs for user sessions. They cannot be revoked easily, they bloat header sizes, and increase XSS vulnerability risk.",
        "predicted_score": 8.8,
        "actual_views": 18500,
        "retention": 0.88,
        "watch_time": 555.0,
        "CTR": 0.14,
        "likes": 1250,
        "comments": 110,
        "shares": 180,
        "category": "viral"
    },
    {
        "clip_id": "hist_clip_010",
        "title": "How SQLite locking works",
        "transcript": "SQLite uses database-level locks. Shared locks allow multiple readers, while exclusive locks block everything during write commits.",
        "predicted_score": 5.2,
        "actual_views": 1500,
        "retention": 0.45,
        "watch_time": 45.0,
        "CTR": 0.04,
        "likes": 35,
        "comments": 4,
        "shares": 2,
        "category": "underperforming"
    },
    {
        "clip_id": "hist_clip_011",
        "title": "FastAPI lifecycle events guide",
        "transcript": "Use lifespan events in FastAPI instead of startup/shutdown events. Seeding database connections is much cleaner this way.",
        "predicted_score": 6.2,
        "actual_views": 3200,
        "retention": 0.58,
        "watch_time": 96.0,
        "CTR": 0.06,
        "likes": 120,
        "comments": 10,
        "shares": 8,
        "category": "standard"
    },
    {
        "clip_id": "hist_clip_012",
        "title": "Avoid circular imports in python",
        "transcript": "Circular imports occur when two modules import each other. To fix this, import within functions or refactor dependencies.",
        "predicted_score": 6.0,
        "actual_views": 2900,
        "retention": 0.55,
        "watch_time": 87.0,
        "CTR": 0.055,
        "likes": 98,
        "comments": 6,
        "shares": 5,
        "category": "standard"
    },
    {
        "clip_id": "hist_clip_013",
        "title": "Python lists memory overhead",
        "transcript": "Python lists allocate extra memory to allow O(1) appends. This dynamic array resizing overhead is called list over-allocation.",
        "predicted_score": 5.8,
        "actual_views": 2100,
        "retention": 0.52,
        "watch_time": 63.0,
        "CTR": 0.048,
        "likes": 75,
        "comments": 5,
        "shares": 3,
        "category": "standard"
    },
    {
        "clip_id": "hist_clip_014",
        "title": "Docker multi-stage build speedup",
        "transcript": "Optimize your Docker image sizes with multi-stage builds. Copy compiled binaries from build stage to a slim runtime image.",
        "predicted_score": 8.2,
        "actual_views": 10500,
        "retention": 0.76,
        "watch_time": 315.0,
        "CTR": 0.095,
        "likes": 560,
        "comments": 35,
        "shares": 60,
        "category": "viral"
    },
    {
        "clip_id": "hist_clip_015",
        "title": "Avoid requirements txt wildcard",
        "transcript": "Pin your dependencies in requirements.txt. Never write wildcards or package versions without bounds to prevent breaking upgrades.",
        "predicted_score": 4.8,
        "actual_views": 950,
        "retention": 0.38,
        "watch_time": 28.5,
        "CTR": 0.025,
        "likes": 18,
        "comments": 1,
        "shares": 1,
        "category": "underperforming"
    }
]


def get_benchmark_dataset() -> List[Dict[str, Any]]:
    """Returns the full offline benchmark dataset."""
    return HISTORICAL_CLIPS
