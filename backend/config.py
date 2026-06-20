"""
Configuration management for AthleAgent backend.
Loads settings from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


def _default_firebase_service_account_key() -> Optional[str]:
    """If `backend/firebase-key.json` exists, use it (file must stay untracked)."""
    p = Path(__file__).resolve().parent / "firebase-key.json"
    return str(p) if p.is_file() else None


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    ENABLE_LEGACY_SKLEARN_ENDPOINT: bool = False

    # sklearn model artifact (default: backend/injury_model.pkl)
    MODEL_PATH: str = str(
        Path(__file__).resolve().parent.parent
        / "ML_model"
        / "artifacts"
        / "20260512_075115"
        / "injury_model.pkl"
    )

    # Google OAuth (optional; used by external/google_auth helpers)
    GOOGLE_CLIENT_ID: Optional[str] = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: Optional[str] = os.getenv("GOOGLE_CLIENT_SECRET")

    # Firebase Admin / Firestore (override via env / `.env`; optional local default above)
    FIREBASE_SERVICE_ACCOUNT_KEY: Optional[str] = Field(
        default_factory=_default_firebase_service_account_key
    )

    # Gemini AI
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

    # File Uploads
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads/images")
    MAX_UPLOAD_SIZE: int = int(os.getenv("MAX_UPLOAD_SIZE", "10485760"))  # 10MB

    # API
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "AthleAgent API"
    VERSION: str = "1.0.0"

    # CORS
    CORS_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:8000",
    ]

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()

# Create upload directory if it doesn't exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
