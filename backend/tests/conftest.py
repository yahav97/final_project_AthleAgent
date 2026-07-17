"""Shared pytest fixtures for backend unit and integration tests."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from config import settings

# Keep pytest output on stdout only — do not append to logs/athleagent.log.
settings.LOG_TO_FILE = False
from utils.logging import setup_logging

setup_logging()

from api.routes import predict as predict_routes
from main import app
from schemas.inference import InjuryPredictionRequest
from services.model_features import DEFAULT_FEATURE_VALUES, MODEL_FEATURE_COLUMNS

SUCCESSFUL_PREDICTION: dict[str, Any] = {
    "risk_level": "Medium",
    "risk_score": 0.42,
    "prediction_confidence": 72.5,
}


@pytest.fixture
def api_client() -> Iterator[TestClient]:
    """FastAPI TestClient with startup/shutdown lifespan (model load)."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
def mock_daily_prediction_pipeline(monkeypatch) -> Callable[..., dict[str, bool]]:
    """Patch POST /predict/daily dependencies for deterministic HTTP tests."""

    def apply(
        *,
        prediction_result: dict[str, Any] | None = None,
        predict_raises: Exception | None = None,
        persist_succeeds: bool = True,
    ) -> dict[str, bool]:
        called = {"predicted": False, "persisted": False}
        result = prediction_result or dict(SUCCESSFUL_PREDICTION)

        def _run_daily(user_id: str, date_key: str) -> dict[str, Any]:
            called["predicted"] = True
            if predict_raises is not None:
                raise predict_raises
            if persist_succeeds:
                called["persisted"] = True
            return dict(result)

        monkeypatch.setattr(predict_routes, "run_daily_prediction", _run_daily)
        return called

    return apply


@pytest.fixture
def mock_firestore_snapshot(monkeypatch, firestore_snapshot: dict[str, Any]) -> Callable[..., None]:
    """Patch Firestore fetch used by the prediction service layer."""

    def apply(snapshot: dict[str, Any] | None = None) -> None:
        data = snapshot if snapshot is not None else firestore_snapshot
        monkeypatch.setattr(
            "services.prediction.service.fetch_inference_firestore_bundle",
            lambda uid, d, **kwargs: {
                "snapshot": dict(data),
                "history_context": {"confidence": "low", "features": {}},
            },
        )

    return apply


@pytest.fixture
def mock_model_gate(monkeypatch) -> Callable[..., None]:
    """Force model loader gate state inside prediction.service."""

    def apply(*, live: bool, gate_reason: str = "none") -> None:
        if live:
            monkeypatch.setattr("services.prediction.service.get_model", lambda: object())
            monkeypatch.setattr("services.prediction.service.get_model_gate_reason", lambda: "none")
        else:
            monkeypatch.setattr("services.prediction.service.get_model", lambda: None)
            monkeypatch.setattr(
                "services.prediction.service.get_model_gate_reason",
                lambda: gate_reason,
            )

    return apply


@pytest.fixture
def sample_prediction_request() -> InjuryPredictionRequest:
    """Typical daily payload with load + recovery signals."""
    return InjuryPredictionRequest(
        userId="test-athlete-001",
        date="2026-05-09",
        age=28,
        historyInjuryCount=1,
        sleepMinutes=450,
        steps=8200,
        distanceMeters=6500,
        activeCalories=520,
        totalCalories=2800,
        bmrCalories=1650,
        heartRateAvg=58,
        restingHeartRate=52,
        hrvRmssd=68.0,
        stressLevel=35,
        muscleSoreness=3,
        energyLevel=65,
        totalProtein=120,
        totalCarbs=280,
        mealsLoggedCount=3,
        nutritionTotalCalories=2400.0,
    )


@pytest.fixture
def minimal_prediction_request() -> InjuryPredictionRequest:
    """Bare-minimum trigger fields (Firestore path fills the rest)."""
    return InjuryPredictionRequest(userId="u1", date="2026-04-30")


@pytest.fixture
def firestore_snapshot() -> dict[str, Any]:
    """Representative Firestore daily snapshot for merge-policy tests."""
    return {
        "profile": {"birth_date": "1995-01-01", "historyInjuryCount": 2},
        "daily_health": {"sleepMinutes": 480, "steps": 50},
        "daily_health_yesterday": {
            "steps": 8300,
            "distanceMeters": 7200,
            "sleepMinutes": 360,
            "heartRateAvg": 58,
            "restingHeartRate": 51,
            "hrvRmssd": 65.0,
        },
        "daily_checkins": {
            "muscleSoreness": 3,
            "stressLevel": 35,
            "energyLevel": 60,
            "injuredYesterday": 0,
        },
        "daily_nutrition_yesterday": {
            "totalProtein": 130,
            "totalCarbs": 290,
            "mealsLoggedCount": 3,
            "totalCalories": 2550,
        },
    }


@pytest.fixture
def mock_model_bundle() -> dict[str, Any]:
    """In-memory sklearn bundle matching production contract."""

    class _MockEstimator:
        feature_names_in_ = np.array(MODEL_FEATURE_COLUMNS, dtype=object)

        def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
            return np.array([[0.65, 0.42]])

    return {
        "estimator": _MockEstimator(),
        "feature_columns": list(MODEL_FEATURE_COLUMNS),
        "threshold": 0.35,
        "medium_threshold": 0.20,
        "winner": "ExtraTrees",
    }


@pytest.fixture
def model_feature_row() -> pd.DataFrame:
    """Single valid model row with population-default values."""
    return pd.DataFrame([dict(DEFAULT_FEATURE_VALUES)], columns=MODEL_FEATURE_COLUMNS)
