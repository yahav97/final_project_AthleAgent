"""Backend configuration — defaults live here; edit for local dev."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent


def _project_root() -> Path:
    return _BACKEND_DIR.parent


def _default_firebase_key() -> Path | None:
    """Service account path from env or backend/firebase-key.json if present."""
    for env_name in ("FIREBASE_SERVICE_ACCOUNT_KEY", "GOOGLE_APPLICATION_CREDENTIALS"):
        raw = os.environ.get(env_name, "").strip()
        if raw:
            return Path(raw)
    bundled = _BACKEND_DIR / "firebase-key.json"
    return bundled if bundled.is_file() else None


@dataclass
class Settings:
    # App
    APP_ENV: str = "development"
    ENABLE_TEST_PREDICT_ENDPOINT: bool = False
    PROJECT_NAME: str = "AthleAgent API"
    VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    API_V1_PREFIX: str = "/api/v1"

    # ML gates — keep aligned with ML_model/policy_config.py
    MODEL_PATH: Path | None = None
    ML_MIN_RECALL_HARD: float = 0.80
    ML_MIN_AUC_FOR_LIVE: float = 0.68

    # Risk bands — aligned with Android UI
    RISK_HIGH_CUTOFF: float = 0.70
    RISK_MEDIUM_CUTOFF: float = 0.20

    # Firestore history window
    HISTORY_LOOKBACK_DAYS: int = 7
    HISTORY_CONFIDENCE_HIGH_MIN_DAYS: int = 7
    HISTORY_CONFIDENCE_MEDIUM_MIN_DAYS: int = 4
    HISTORY_MIN_WATCH_SYNC_SIGNAL_GROUPS: int = 3

    # Sleep / recovery features — aligned with ML_model/policy_config.py
    SLEEP_TARGET_HOURS: float = 8.0
    SLEEP_DEBT_SINGLE_DAY_PROXY_SCALE: float = 1.25

    # Prediction confidence blend
    CONFIDENCE_HISTORY_WEIGHT: float = 0.6
    CONFIDENCE_QUALITY_WEIGHT: float = 0.4
    CONFIDENCE_SCORE_HIGH: float = 0.95
    CONFIDENCE_SCORE_MEDIUM: float = 0.70
    CONFIDENCE_SCORE_LOW: float = 0.45

    # Nutrition imputation when meals are missing
    NUTRITION_DEFAULT_PROTEIN: int = 130
    NUTRITION_DEFAULT_CARBS: int = 300
    NUTRITION_DEFAULT_MEALS_LOGGED: int = 3
    NUTRITION_DEFAULT_CALORIES: int = 2600

    # Profile imputation
    PROFILE_DEFAULT_AGE: int = 22

    # HTTP / dev helpers
    SLOW_REQUEST_MS: int = 2000
    REQUEST_LOG_SKIP_PATHS: tuple[str, ...] = (
        "/health",
        "/",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/status/ml",
    )
    TEST_PREDICT_MOCK_RISK_PERCENTAGE: float = 72.5

    # Firebase
    FIREBASE_SERVICE_ACCOUNT_KEY: Path | None = field(default_factory=_default_firebase_key)
    GOOGLE_APPLICATION_CREDENTIALS: Path | None = None

    # Logging
    LOG_DIR: Path = field(default_factory=lambda: _project_root() / "logs")
    LOG_TO_FILE: bool = True
    LOG_FILE_NAME: str = "athleagent.log"
    LOG_LEVEL: str = "INFO"
    LOG_MAX_BYTES: int = 10_000_000
    LOG_BACKUP_COUNT: int = 5

    # Client telemetry rate limits (seconds between duplicate events)
    CLIENT_EVENT_RATE_LIMIT_SCREEN_SEC: int = 30
    CLIENT_EVENT_RATE_LIMIT_ACTION_SEC: int = 10
    CLIENT_EVENT_RATE_LIMIT_SYNC_SEC: int = 15
    CLIENT_EVENT_RATE_LIMIT_ML_TRIGGER_SEC: int = 5
    CLIENT_EVENT_MAX_TRACKED_KEYS: int = 10_000
    CLIENT_EVENT_STALE_ENTRY_SECONDS: int = 86_400

    # CORS (web dev origins only)
    CORS_ORIGINS: list[str] = field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:8080"]
    )

    @property
    def openapi_enabled(self) -> bool:
        return self.APP_ENV == "development"


settings = Settings()
