"""
Configuration management for AthleAgent backend.

All tunable application behaviour lives here. Override via environment variables
or a `.env` file in `backend/` (preferred) or the process working directory.

Policy map (where each group is used in code):
┌─────────────────────────────┬──────────────────────────────────────────┐
│ Settings group              │ Consumed by                              │
├─────────────────────────────┼──────────────────────────────────────────┤
│ ML_MIN_* / ML_DEGRADED_*      │ ml/model_loader.py — live model gates    │
│ RISK_*_CUTOFF               │ services/risk_levels.py                  │
│ HISTORY_*                   │ history/repository.py, day_quality.py    │
│ SLEEP_*                     │ feature_engineering.py, rolling_features │
│ CONFIDENCE_*                │ prediction/confidence.py                 │
│ NUTRITION_DEFAULT_*         │ nutrition_defaults.py                    │
└─────────────────────────────┴──────────────────────────────────────────┘

Prediction confidence blend (see ``compute_prediction_confidence_percent``):
  (CONFIDENCE_HISTORY_WEIGHT × history_score + CONFIDENCE_QUALITY_WEIGHT × quality_score) × 100
  Example high history + strong inputs: (0.6×0.95 + 0.4×1.0)×100 ≈ 97
"""

from __future__ import annotations

import json
import sys
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


def _ml_policy_config_defaults() -> tuple[float, float, float, float]:
    """Load ML policy and feature-engineering defaults from ML_model/policy_config.py."""
    ml_root = str(_project_root() / "ML_model")
    if ml_root not in sys.path:
        sys.path.insert(0, ml_root)
    try:
        from policy_config import (
            DEFAULT_MIN_AUC_FOR_LIVE,
            DEFAULT_MIN_RECALL_HARD,
            DEFAULT_SLEEP_DEBT_SINGLE_DAY_PROXY_SCALE,
            DEFAULT_SLEEP_TARGET_HOURS,
        )

        return (
            DEFAULT_MIN_RECALL_HARD,
            DEFAULT_MIN_AUC_FOR_LIVE,
            DEFAULT_SLEEP_TARGET_HOURS,
            DEFAULT_SLEEP_DEBT_SINGLE_DAY_PROXY_SCALE,
        )
    except ImportError:
        return 0.80, 0.68, 8.0, 1.25


(
    _ML_DEFAULT_RECALL_HARD,
    _ML_DEFAULT_AUC_FOR_LIVE,
    _ML_DEFAULT_SLEEP_TARGET_HOURS,
    _ML_DEFAULT_SLEEP_DEBT_SINGLE_DAY_PROXY_SCALE,
) = _ml_policy_config_defaults()


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
    APP_ENV: Literal["development", "demo", "production"] = "development"
    ENABLE_TEST_PREDICT_ENDPOINT: bool = False
    REQUIRE_FIREBASE_AUTH: bool = False

    # -------------------------------------------------------------------------
    # ML model loading & live gates (see backend/docs/MODEL.md)
    # -------------------------------------------------------------------------
    # Defaults synced with ML_model/policy_config.py (override via .env in staging).
    MODEL_PATH: Path | None = None
    ML_MIN_RECALL_HARD: float = _ML_DEFAULT_RECALL_HARD
    ML_MIN_AUC_FOR_LIVE: float = _ML_DEFAULT_AUC_FOR_LIVE
    ML_DEGRADED_AUC_OFFSET: float = 0.02

    # -------------------------------------------------------------------------
    # Risk classification — must stay aligned with Android UI bands
    # (see services/risk_levels.py docstring)
    # -------------------------------------------------------------------------
    RISK_HIGH_CUTOFF: float = 0.70
    RISK_MEDIUM_CUTOFF: float = 0.20

    # -------------------------------------------------------------------------
    # Firestore history window & confidence policy
    # (see history/repository.py, history/day_quality.py, prediction/confidence.py)
    # -------------------------------------------------------------------------
    HISTORY_LOOKBACK_DAYS: int = Field(
        default=7,
        description="Days fetched for rolling ACWR / sleep debt / HRV features.",
    )
    HISTORY_CONFIDENCE_HIGH_MIN_DAYS: int = Field(
        default=7,
        description="Quality watch-sync days (in lookback) required for HistoryConfidence.HIGH.",
    )
    HISTORY_CONFIDENCE_MEDIUM_MIN_DAYS: int = Field(
        default=4,
        description="Quality days for HistoryConfidence.MEDIUM (below HIGH threshold).",
    )
    HISTORY_MIN_WATCH_SYNC_SIGNAL_GROUPS: int = Field(
        default=3,
        description=(
            "Per merged wake-up day: min categories with data among "
            "load / sleep / heart / energy (4 total) to count as a quality day."
        ),
    )

    # -------------------------------------------------------------------------
    # Sleep / recovery feature engineering (see ML_model/policy_config.py)
    # -------------------------------------------------------------------------
    # Defaults synced with training; override via .env for staging experiments.
    SLEEP_TARGET_HOURS: float = _ML_DEFAULT_SLEEP_TARGET_HOURS
    SLEEP_DEBT_SINGLE_DAY_PROXY_SCALE: float = _ML_DEFAULT_SLEEP_DEBT_SINGLE_DAY_PROXY_SCALE

    # -------------------------------------------------------------------------
    # Prediction confidence scoring (history window × same-day input completeness)
    # Formula: (HISTORY_WEIGHT×history_score + QUALITY_WEIGHT×quality_score) × 100
    # -------------------------------------------------------------------------
    CONFIDENCE_HISTORY_WEIGHT: float = Field(default=0.6, description="Weight of 7-day history confidence.")
    CONFIDENCE_QUALITY_WEIGHT: float = Field(default=0.4, description="Weight of same-day data quality score.")
    CONFIDENCE_SCORE_HIGH: float = Field(
        default=0.95,
        description="History score when Firestore window is HIGH (7+ quality days).",
    )
    CONFIDENCE_SCORE_MEDIUM: float = Field(default=0.70, description="History score for MEDIUM window.")
    CONFIDENCE_SCORE_LOW: float = Field(default=0.45, description="History score for LOW / new athlete.")

    # -------------------------------------------------------------------------
    # Nutrition imputation when a day has no logged meals
    # -------------------------------------------------------------------------
    # Medians from ML_model/data_generator.py synthetic cohort (seed=42).
    NUTRITION_DEFAULT_PROTEIN: int = 130
    NUTRITION_DEFAULT_CARBS: int = 300
    NUTRITION_DEFAULT_MEALS_LOGGED: int = 3
    NUTRITION_DEFAULT_CALORIES: int = 2600

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
    # Web dev origins only — must not include the API port (PORT, default 8000).
    CORS_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://localhost:8080",
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
