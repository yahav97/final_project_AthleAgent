"""HTTP-level inference edge cases."""

import pytest
from fastapi.testclient import TestClient

from main import app
from schemas.inference import InjuryPredictionRequest
from services.prediction.service import predict_injury_risk
from utils.exceptions import MLModelError, ValidationError

pytestmark = pytest.mark.integration

_BASE_PAYLOAD = dict(
    userId="edge_case",
    date="2026-04-30",
    age=28,
    sleepMinutes=420,
    steps=9000,
    distanceMeters=7000,
    stressLevel=40,
    muscleSoreness=3,
    energyLevel=70,
)


def test_predict_zero_sleep_passes_through_when_model_blocked(monkeypatch):
    """Zero sleep lowers quality score but still reaches model gate (not HTTP 422)."""
    monkeypatch.setattr("services.prediction.service.get_model", lambda: None)
    monkeypatch.setattr(
        "services.prediction.service.get_model_gate_reason",
        lambda: "manifest_corrupted",
    )
    with pytest.raises(MLModelError, match="Model is not live: manifest_corrupted"):
        predict_injury_risk(InjuryPredictionRequest(**{**_BASE_PAYLOAD, "sleepMinutes": 0}))


def test_predict_missing_age_raises_validation_error():
    with pytest.raises(ValidationError, match="age is required"):
        predict_injury_risk(
            InjuryPredictionRequest(
                userId="minimal",
                date="2026-04-30",
                sleepMinutes=420,
                steps=5000,
            )
        )


def test_status_endpoint_multiple_calls_light_load():
    with TestClient(app) as client:
        for _ in range(10):
            response = client.get("/status/ml")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] in ("Live", "Blocked")
