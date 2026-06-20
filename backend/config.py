"""
Configuration management for AthleAgent backend.
Loads settings from environment variables with sensible defaults.
"""

import json
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _default_firebase_service_account_key() -> Path | None:
    """If `backend/firebase-key.json` exists, use it (file must stay untracked)."""
    p = Path(__file__).resolve().parent / "firebase-key.json"
    return p if p.is_file() else None


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    ENABLE_LEGACY_SKLEARN_ENDPOINT: bool = False

    # None → ml.model_loader resolves promoted.json, then backend/injury_model.pkl
    MODEL_PATH: Path | None = None

    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None

    FIREBASE_SERVICE_ACCOUNT_KEY: Path | None = Field(
        default_factory=_default_firebase_service_account_key
    )
    GOOGLE_APPLICATION_CREDENTIALS: Path | None = None

    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-1.5-pro"

    UPLOAD_DIR: Path = Path("./uploads/images")
    MAX_UPLOAD_SIZE: int = 10_485_760

    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "AthleAgent API"
    VERSION: str = "1.0.0"

    CORS_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:8000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                return json.loads(stripped)
            return [part.strip() for part in stripped.split(",") if part.strip()]
        return value


settings = Settings()
