"""Backend configuration — defaults here; override via env / `.env` / Docker."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent


def _project_root() -> Path:
    return _BACKEND_DIR.parent


def _default_log_dir() -> Path:
    return _project_root() / "logs"


class Settings(BaseSettings):
    """Tunable backend settings. Environment variables and `.env` override defaults."""

    model_config = SettingsConfigDict(
        env_file=(
            _BACKEND_DIR / ".env",
            _project_root() / ".env",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
        # Allow tests / conftest to mutate flags like LOG_TO_FILE.
        validate_assignment=True,
    )

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
    REQUEST_LOG_SKIP_PATHS: Annotated[tuple[str, ...], NoDecode] = (
        "/health",
        "/",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/status/ml",
    )
    TEST_PREDICT_MOCK_RISK_PERCENTAGE: float = 72.5

    # Firebase
    FIREBASE_SERVICE_ACCOUNT_KEY: Path | None = None
    GOOGLE_APPLICATION_CREDENTIALS: Path | None = None

    # Logging
    LOG_DIR: Path = Field(default_factory=_default_log_dir)
    LOG_TO_FILE: bool = True
    LOG_FILE_NAME: str = "athleagent.log"
    LOG_LEVEL: str = "INFO"
    LOG_RETENTION_DAYS: int = 7

    # Client telemetry rate limits (seconds between duplicate events)
    CLIENT_EVENT_RATE_LIMIT_SCREEN_SEC: int = 30
    CLIENT_EVENT_RATE_LIMIT_ACTION_SEC: int = 10
    CLIENT_EVENT_RATE_LIMIT_SYNC_SEC: int = 15
    CLIENT_EVENT_RATE_LIMIT_ML_TRIGGER_SEC: int = 5
    CLIENT_EVENT_MAX_TRACKED_KEYS: int = 10_000
    CLIENT_EVENT_STALE_ENTRY_SECONDS: int = 86_400

    # CORS (web dev origins only) — env: comma-separated list
    CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:8080"]
    )

    @field_validator(
        "MODEL_PATH",
        "FIREBASE_SERVICE_ACCOUNT_KEY",
        "GOOGLE_APPLICATION_CREDENTIALS",
        mode="before",
    )
    @classmethod
    def _empty_optional_path(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @field_validator("REQUEST_LOG_SKIP_PATHS", mode="before")
    @classmethod
    def _parse_skip_paths(cls, value: Any) -> Any:
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split(",") if part.strip())
        if isinstance(value, list):
            return tuple(value)
        return value

    @model_validator(mode="after")
    def _resolve_firebase_key(self) -> Settings:
        """Prefer explicit key path; else GOOGLE_APPLICATION_CREDENTIALS; else bundled file."""
        if self.FIREBASE_SERVICE_ACCOUNT_KEY is not None:
            return self
        if self.GOOGLE_APPLICATION_CREDENTIALS is not None:
            self.FIREBASE_SERVICE_ACCOUNT_KEY = self.GOOGLE_APPLICATION_CREDENTIALS
            return self
        bundled = _BACKEND_DIR / "firebase-key.json"
        if bundled.is_file():
            self.FIREBASE_SERVICE_ACCOUNT_KEY = bundled
        return self

    @property
    def openapi_enabled(self) -> bool:
        return self.APP_ENV == "development"


settings = Settings()
