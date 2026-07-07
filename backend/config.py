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
