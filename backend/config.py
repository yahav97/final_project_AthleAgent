"""
Configuration management for AthleAgent backend.

All tunable application behaviour lives here. Override via environment variables
or a `.env` file in `backend/` (preferred) or the process working directory.

Domain constants (risk bands, ML gates, history windows) are grouped below so
staging and future tuning do not require hunting through service modules.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent


def _default_firebase_service_account_key() -> Path | None:
    """If `backend/firebase-key.json` exists, use it (file must stay untracked)."""
    p = _BACKEND_DIR / "firebase-key.json"
    return p if p.is_file() else None


def _project_root() -> Path:
    """Repository root (parent of backend/)."""
    return _BACKEND_DIR.parent


def _default_log_dir() -> Path:
    """Unified system log directory at repo root."""
    return _project_root() / "logs"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(_BACKEND_DIR / ".env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # -------------------------------------------------------------------------
    # Feature flags
    # -------------------------------------------------------------------------
    ENABLE_TEST_PREDICT_ENDPOINT: bool = False

    # -------------------------------------------------------------------------
    # ML model loading & live gates (see backend/docs/MODEL.md)
    # -------------------------------------------------------------------------
    MODEL_PATH: Path | None = None
    ML_MIN_RECALL_HARD: float = 0.80
    ML_MIN_AUC_FOR_LIVE: float = 0.68
    ML_DEGRADED_AUC_OFFSET: float = 0.02

    # -------------------------------------------------------------------------
    # Risk classification — must stay aligned with Android UI bands
    # (see services/risk_levels.py docstring)
    # -------------------------------------------------------------------------
    RISK_HIGH_CUTOFF: float = 0.70
    RISK_MEDIUM_CUTOFF: float = 0.20

    # -------------------------------------------------------------------------
    # Firestore history window & confidence policy
    # -------------------------------------------------------------------------
    HISTORY_LOOKBACK_DAYS: int = 7
    HISTORY_CONFIDENCE_HIGH_MIN_DAYS: int = 7
    HISTORY_CONFIDENCE_MEDIUM_MIN_DAYS: int = 4

    # -------------------------------------------------------------------------
    # Prediction confidence scoring (history window × input completeness)
    # -------------------------------------------------------------------------
    CONFIDENCE_HISTORY_WEIGHT: float = 0.6
    CONFIDENCE_QUALITY_WEIGHT: float = 0.4
    CONFIDENCE_SCORE_HIGH: float = 0.95
    CONFIDENCE_SCORE_MEDIUM: float = 0.70
    CONFIDENCE_SCORE_LOW: float = 0.45

    # -------------------------------------------------------------------------
    # Nutrition imputation when a day has no logged meals
    # -------------------------------------------------------------------------
    NUTRITION_DEFAULT_PROTEIN: int = 125
    NUTRITION_DEFAULT_CARBS: int = 290
    NUTRITION_DEFAULT_MEALS_LOGGED: int = 3
    NUTRITION_DEFAULT_CALORIES: int = 2500

    # -------------------------------------------------------------------------
    # HTTP middleware & dev-only mock endpoint
    # -------------------------------------------------------------------------
    SLOW_REQUEST_MS: int = 2000
    REQUEST_LOG_SKIP_PATHS: Annotated[list[str], NoDecode] = [
        "/health",
        "/",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/status/ml",
    ]
    TEST_PREDICT_MOCK_RISK_PERCENTAGE: float = 72.5

    # -------------------------------------------------------------------------
    # Firebase / Google Cloud (backend)
    # -------------------------------------------------------------------------
    FIREBASE_SERVICE_ACCOUNT_KEY: Path | None = Field(
        default_factory=_default_firebase_service_account_key
    )
    GOOGLE_APPLICATION_CREDENTIALS: Path | None = None

    # Reserved for future OAuth routes (see external/google_auth.py)
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None

    # -------------------------------------------------------------------------
    # API metadata
    # -------------------------------------------------------------------------
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "AthleAgent API"
    VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------
    LOG_DIR: Path = Field(default_factory=_default_log_dir)
    LOG_FILE_NAME: str = "athleagent.log"
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["text", "json"] = "json"
    LOG_MAX_BYTES: int = 10_000_000
    LOG_BACKUP_COUNT: int = 5

    # -------------------------------------------------------------------------
    # Client telemetry rate limiting (POST /api/v1/observability/client-events)
    # -------------------------------------------------------------------------
    CLIENT_EVENT_RATE_LIMIT_SCREEN_SEC: int = 30
    CLIENT_EVENT_RATE_LIMIT_ACTION_SEC: int = 10
    CLIENT_EVENT_RATE_LIMIT_SYNC_SEC: int = 15
    CLIENT_EVENT_RATE_LIMIT_ML_TRIGGER_SEC: int = 5
    CLIENT_EVENT_MAX_TRACKED_KEYS: int = 10_000
    CLIENT_EVENT_STALE_ENTRY_SECONDS: int = 86_400

    # -------------------------------------------------------------------------
    # CORS
    # -------------------------------------------------------------------------
    CORS_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:8000",
    ]

    @field_validator("CORS_ORIGINS", "REQUEST_LOG_SKIP_PATHS", mode="before")
    @classmethod
    def _parse_string_list_env(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                return json.loads(stripped)
            return [part.strip() for part in stripped.split(",") if part.strip()]
        return value


settings = Settings()
