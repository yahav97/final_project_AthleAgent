"""Ensure predict_proba receives only columns the saved estimator was fit on."""

from pathlib import Path

import pytest

from schemas.inference import InjuryPredictionRequest
from services.prediction_service import predict_injury_risk


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[1] / "injury_model.pkl").is_file(),
    reason="injury_model.pkl not present",
)
def test_predict_injury_risk_with_loaded_model_no_500():
    from fastapi.testclient import TestClient

    from main import app

    with TestClient(app) as client:
        r = client.post(
            "/predict",
            json={"sleepMinutes": 480, "steps": 8000, "stressLevel": 35, "muscleSoreness": 2},
        )
    assert r.status_code == 200
    data = r.json()
    assert "artifact" not in data.get("recommendation", "").lower()
    assert 0.0 <= float(data["risk_score"]) <= 1.0


def test_predict_injury_risk_service_subset_columns_skips_missing_estimator(monkeypatch):
    """When no model, service returns demo dict without calling sklearn."""
    from services import prediction_service as ps

    monkeypatch.setattr(ps, "get_model", lambda: None)
    out = predict_injury_risk(InjuryPredictionRequest(sleepMinutes=480))
    assert out["risk_score"] == 0.12
    assert "artifact" in out["recommendation"].lower()
