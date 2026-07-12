"""
Centralized application configuration.
Reads from environment variables with sensible defaults for local development.
"""

import os
from dotenv import load_dotenv

# Load .env file (no-op if it doesn't exist)
load_dotenv()


class Settings:
    """Application settings derived from environment variables."""

    @property
    def APP_ENV(self) -> str:
        """Application environment: 'development', 'beta', or 'production'."""
        return os.getenv("APP_ENV", "development").lower()

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_beta(self) -> bool:
        return self.APP_ENV == "beta"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    # --- API Keys ---

    @property
    def GEMINI_API_KEY(self) -> str:
        return os.getenv("GEMINI_API_KEY", "")

    # --- YouTube OAuth ---

    @property
    def YOUTUBE_CLIENT_ID(self) -> str:
        return os.getenv("YOUTUBE_CLIENT_ID", "")

    @property
    def YOUTUBE_CLIENT_SECRET(self) -> str:
        return os.getenv("YOUTUBE_CLIENT_SECRET", "")

    @property
    def YOUTUBE_REDIRECT_URI(self) -> str:
        """Explicit redirect URI override. If empty, derived from request base URL."""
        return os.getenv("YOUTUBE_REDIRECT_URI", "")

    # --- Encryption ---

    @property
    def ENCRYPTION_KEY(self) -> str:
        return os.getenv("ENCRYPTION_KEY", "")

    # --- CORS ---

    @property
    def ALLOWED_ORIGINS(self) -> list[str]:
        """Comma-separated list of allowed CORS origins."""
        raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000,null")
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    # --- HTTPS ---

    @property
    def ENFORCE_HTTPS(self) -> bool:
        return os.getenv("ENFORCE_HTTPS", "false").lower() == "true"

    # --- Database ---

    @property
    def DATABASE_URL(self) -> str:
        return os.getenv("DATABASE_URL", "sqlite:///output/analytics.db")

    # --- Local Music Library Settings ---

    @property
    def MUSIC_ENABLED(self) -> bool:
        return os.getenv("MUSIC_ENABLED", "true").lower() == "true"

    @property
    def MUSIC_LIBRARY_PATH(self) -> str:
        return os.getenv("MUSIC_LIBRARY_PATH", "assets/music")

    @property
    def VIDEO_UPSCALE_MODE(self) -> str:
        """Video upscaling mode: Off, 2x AI Upscale, 4K AI Upscale, 8K AI Upscale"""
        return os.getenv("VIDEO_UPSCALE_MODE", "Off").strip()

    @property
    def DEFAULT_MUSIC_VOLUME(self) -> int:
        try:
            return int(os.getenv("DEFAULT_MUSIC_VOLUME", "15"))
        except ValueError:
            return 15

    @property
    def RANDOMIZE_TRACKS(self) -> bool:
        return os.getenv("RANDOMIZE_TRACKS", "true").lower() == "true"

    # ── Audit 1: LLM Model Names ──────────────────────────────────────────────
    # These control which AI models are used at each pipeline stage.
    # Override via environment variables to switch providers without code changes.

    @property
    def SCOUT_MODEL(self) -> str:
        """Fast/cheap model for initial clip scouting and emotion analysis."""
        return os.getenv("SCOUT_MODEL", "claude-haiku-4-5")

    @property
    def VIRALITY_MODEL(self) -> str:
        """Model used to score virality potential of each candidate clip."""
        return os.getenv("VIRALITY_MODEL", "claude-haiku-4-5")

    @property
    def CURATOR_MODEL(self) -> str:
        """High-quality model for final clip curation and selection."""
        return os.getenv("CURATOR_MODEL", "claude-sonnet-4-6")

    @property
    def EDITOR_MODEL(self) -> str:
        """High-quality model for upload package generation (title/description/hashtags)."""
        return os.getenv("EDITOR_MODEL", "claude-sonnet-4-6")

    @property
    def OPENAI_MODEL(self) -> str:
        """OpenAI model used when an OpenAI API key is active."""
        return os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    @property
    def GEMINI_MODEL(self) -> str:
        """Gemini model used when a Google API key is active."""
        return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    @property
    def ANTHROPIC_MODEL(self) -> str:
        """Primary Anthropic model. If unavailable, ANTHROPIC_FALLBACK_MODELS are tried."""
        return os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    @property
    def ANTHROPIC_FALLBACK_MODELS(self) -> list[str]:
        """Ordered list of fallback Anthropic models tried if the primary is unavailable."""
        raw = os.getenv(
            "ANTHROPIC_FALLBACK_MODELS",
            "claude-3-5-sonnet-20241022,claude-3-5-sonnet-latest,claude-3-5-sonnet-20240620,claude-3-haiku-20240307"
        )
        return [m.strip() for m in raw.split(",") if m.strip()]

    # ── Audit 1: Clip Duration Thresholds ─────────────────────────────────────
    # All durations in seconds. Platform limit is ~60 s for YouTube Shorts.

    @property
    def MIN_CLIP_DURATION_SECS(self) -> float:
        """Minimum acceptable clip duration. Clips shorter than this are rejected."""
        try:
            return float(os.getenv("MIN_CLIP_DURATION_SECS", "38.0"))
        except ValueError:
            return 38.0

    @property
    def MAX_CLIP_DURATION_SECS(self) -> float:
        """Maximum clip duration. 2-second buffer under the 60-second Shorts limit."""
        try:
            return float(os.getenv("MAX_CLIP_DURATION_SECS", "58.0"))
        except ValueError:
            return 58.0

    @property
    def DEFAULT_CLIP_DURATION_SECS(self) -> float:
        """Fallback duration used when AI returns invalid clip boundaries."""
        try:
            return float(os.getenv("DEFAULT_CLIP_DURATION_SECS", "35.0"))
        except ValueError:
            return 35.0

    # ── Audit 1: Camera Tracking Constants ────────────────────────────────────
    # These tune the Phase-18 camera tracking algorithm in clipper.py.

    @property
    def CAMERA_MAX_VELOCITY_PX(self) -> int:
        """Maximum horizontal camera travel per frame (px). Prevents jarring cuts."""
        try:
            return int(os.getenv("CAMERA_MAX_VELOCITY_PX", "15"))
        except ValueError:
            return 15

    @property
    def CAMERA_DEAD_ZONE_PX(self) -> int:
        """Ignore face-center shifts smaller than this (px). Prevents micro-jitter."""
        try:
            return int(os.getenv("CAMERA_DEAD_ZONE_PX", "60"))
        except ValueError:
            return 60

    @property
    def CAMERA_HEADROOM_FRACTION(self) -> float:
        """Fraction of face height to leave above the face (headroom)."""
        try:
            return float(os.getenv("CAMERA_HEADROOM_FRACTION", "0.12"))
        except ValueError:
            return 0.12

    @property
    def CAMERA_FACE_DRIFT_SPEED(self) -> float:
        """Fraction per frame to drift the crop toward center when no face is detected."""
        try:
            return float(os.getenv("CAMERA_FACE_DRIFT_SPEED", "0.04"))
        except ValueError:
            return 0.04

    @property
    def CAMERA_SPEAKER_LOCK_SECS(self) -> float:
        """Seconds a speaker must be continuously active before the camera locks onto them."""
        try:
            return float(os.getenv("CAMERA_SPEAKER_LOCK_SECS", "1.0"))
        except ValueError:
            return 1.0

    @property
    def CAMERA_LIP_HISTORY_FRAMES(self) -> int:
        """Number of frames to average lip-activity variance over."""
        try:
            return int(os.getenv("CAMERA_LIP_HISTORY_FRAMES", "6"))
        except ValueError:
            return 6

    @property
    def CAMERA_LIP_ACTIVITY_WEIGHT(self) -> float:
        """Score multiplier applied when lip activity is detected (favors active speakers)."""
        try:
            return float(os.getenv("CAMERA_LIP_ACTIVITY_WEIGHT", "3.0"))
        except ValueError:
            return 3.0

    @property
    def CAMERA_HOLD_SECS_NO_FACE(self) -> float:
        """Seconds to hold last crop position before drifting when no face is visible."""
        try:
            return float(os.getenv("CAMERA_HOLD_SECS_NO_FACE", "1.5"))
        except ValueError:
            return 1.5

    # ── Audit 1: Subtitle / ASS Constants ─────────────────────────────────────
    # Control ASS subtitle rendering, timing, and dynamic chunking behaviour.

    @property
    def SUBTITLE_CHUNK_SIZE(self) -> int:
        """Default number of words shown on screen per subtitle chunk (legacy; chunking is now dynamic)."""
        try:
            return int(os.getenv("SUBTITLE_CHUNK_SIZE", "2"))
        except ValueError:
            return 2

    @property
    def SUBTITLE_DELAY_SECS(self) -> float:
        """Seconds to shift subtitle start/end times to align with audio."""
        try:
            return float(os.getenv("SUBTITLE_DELAY_SECS", "0.05"))
        except ValueError:
            return 0.05

    @property
    def ASS_PLAY_RES_X(self) -> int:
        """ASS PlayResX — horizontal resolution for the subtitle canvas."""
        try:
            return int(os.getenv("ASS_PLAY_RES_X", "1080"))
        except ValueError:
            return 1080

    @property
    def ASS_PLAY_RES_Y(self) -> int:
        """ASS PlayResY — vertical resolution for the subtitle canvas (9:16 portrait)."""
        try:
            return int(os.getenv("ASS_PLAY_RES_Y", "1920"))
        except ValueError:
            return 1920

    @property
    def SUBTITLE_MAX_WORDS_PER_CHUNK(self) -> int:
        """Maximum words in one subtitle chunk before a forced line-break."""
        try:
            return int(os.getenv("SUBTITLE_MAX_WORDS_PER_CHUNK", "4"))
        except ValueError:
            return 4

    @property
    def SUBTITLE_GAP_SPLIT_SECS(self) -> float:
        """Audio silence gap (seconds) that triggers a subtitle chunk split."""
        try:
            return float(os.getenv("SUBTITLE_GAP_SPLIT_SECS", "0.35"))
        except ValueError:
            return 0.35

    @property
    def SUBTITLE_MAX_DURATION_SECS(self) -> float:
        """Maximum on-screen duration (seconds) for a single subtitle chunk."""
        try:
            return float(os.getenv("SUBTITLE_MAX_DURATION_SECS", "3.0"))
        except ValueError:
            return 3.0

    @property
    def SUBTITLE_WPM_KARAOKE_THRESHOLD(self) -> int:
        """WPM above this triggers karaoke-style word-by-word subtitles."""
        try:
            return int(os.getenv("SUBTITLE_WPM_KARAOKE_THRESHOLD", "200"))
        except ValueError:
            return 200

    @property
    def SUBTITLE_WPM_CLASSIC_THRESHOLD(self) -> int:
        """WPM below this triggers classic (full-phrase at once) subtitles."""
        try:
            return int(os.getenv("SUBTITLE_WPM_CLASSIC_THRESHOLD", "130"))
        except ValueError:
            return 130

    # ── Audit 1: Cache / Disk Management ──────────────────────────────────────

    @property
    def CACHE_MAX_SIZE_BYTES(self) -> int:
        """Maximum cache directory size before pruning is triggered."""
        try:
            return int(os.getenv("CACHE_MAX_SIZE_BYTES", str(5 * 1024 * 1024 * 1024)))
        except ValueError:
            return 5 * 1024 * 1024 * 1024  # 5 GB

    @property
    def CACHE_TARGET_SIZE_BYTES(self) -> int:
        """Target cache size after pruning completes."""
        try:
            return int(os.getenv("CACHE_TARGET_SIZE_BYTES", str(3 * 1024 * 1024 * 1024)))
        except ValueError:
            return 3 * 1024 * 1024 * 1024  # 3 GB

    @property
    def DOWNLOAD_CONCURRENT_FRAGMENTS(self) -> int:
        """Number of parallel fragment downloads for yt-dlp (higher = faster on good connections)."""
        try:
            return int(os.getenv("DOWNLOAD_CONCURRENT_FRAGMENTS", "8"))
        except ValueError:
            return 8

    # ── Audit 1: Job Lifecycle Timers ─────────────────────────────────────────

    @property
    def JOB_CLEANUP_INTERVAL_SECS(self) -> int:
        """How often (seconds) the background cleanup task scans for old jobs."""
        try:
            return int(os.getenv("JOB_CLEANUP_INTERVAL_SECS", "600"))
        except ValueError:
            return 600  # 10 minutes

    @property
    def JOB_TTL_COMPLETED_SECS(self) -> int:
        """How long (seconds) a completed/failed job remains in memory before eviction."""
        try:
            return int(os.getenv("JOB_TTL_COMPLETED_SECS", "3600"))
        except ValueError:
            return 3600  # 1 hour

    @property
    def JOB_TTL_RUNNING_SECS(self) -> int:
        """How long (seconds) a stuck/running job is kept before forced eviction."""
        try:
            return int(os.getenv("JOB_TTL_RUNNING_SECS", "10800"))
        except ValueError:
            return 10800  # 3 hours

    # ── Audit 1: OAuth Security ────────────────────────────────────────────────

    @property
    def OAUTH_STATE_TTL_SECS(self) -> int:
        """Seconds an OAuth CSRF state token remains valid before expiry."""
        try:
            return int(os.getenv("OAUTH_STATE_TTL_SECS", "600"))
        except ValueError:
            return 600  # 10 minutes

    # ── Audit 4: Auto-sync Interval ───────────────────────────────────────────

    @property
    def YOUTUBE_SYNC_INTERVAL_HOURS(self) -> int:
        """How often (hours) the background scheduler automatically syncs YouTube analytics."""
        try:
            return int(os.getenv("YOUTUBE_SYNC_INTERVAL_HOURS", "6"))
        except ValueError:
            return 6

    def validate(self):
        """Validates configuration on startup, raising ValueError on critical misconfigurations in production."""
        if self.APP_ENV == "production":
            # 1. Enforce encryption key in production
            if not self.ENCRYPTION_KEY:
                raise ValueError("ENCRYPTION_KEY environment variable MUST be set in production mode.")
            # Verify Fernet key format
            from cryptography.fernet import Fernet
            try:
                Fernet(self.ENCRYPTION_KEY.encode())
            except Exception as e:
                raise ValueError(f"ENCRYPTION_KEY is not a valid Fernet key: {e}")
                
            # 2. Enforce API keys are preset
            api_key = self.GEMINI_API_KEY or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY or OPENAI_API_KEY environment variable MUST be set in production mode.")
                
            # 3. Enforce YouTube Client Secrets in production
            if not self.YOUTUBE_CLIENT_ID or not self.YOUTUBE_CLIENT_SECRET:
                raise ValueError("YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET must be set in production mode.")


# Global singleton
settings = Settings()
