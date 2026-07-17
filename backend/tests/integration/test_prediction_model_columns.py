"""Integration test: real model artifact + HTTP predict path."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(
    not (_BACKEND_ROOT / "injury_model.pkl").is_file(),
    reason="injury_model.pkl not present",
)
def test_predict_daily_with_loaded_model_no_500(monkeypatch):
    from main import app

    monkeypatch.setattr(
        "services.prediction.service.fetch_inference_firestore_bundle",
        lambda uid, d, **kwargs: {
            "snapshot": {
                "profile": {"birth_date": "1995-01-01"},
                "daily_health": {"sleepMinutes": 480},
                "daily_health_yesterday": {"steps": 8000, "distanceMeters": 5000},
                "daily_checkins": {"stressLevel": 35, "muscleSoreness": 2, "energyLevel": 65},
                "daily_nutrition_yesterday": {},
            },
            "history_context": {"confidence": "low", "features": {}},
        },
    )

    monkeypatch.setattr(
        "services.prediction.service.load_cached_daily_prediction",
        lambda uid, d: None,
    )
    monkeypatch.setattr(
        "services.prediction.service.save_daily_prediction_result_with_retries",
        lambda uid, d, r, **kw: True,
    )

    with TestClient(app) as client:
        r = client.post(
            "/predict/daily",
            json={"userId": "u1", "date": "2026-04-30"},
        )
    if r.status_code == 503:
        assert "Model is not live" in r.json()["detail"]
        return
    assert r.status_code == 200
    data = r.json()
    assert 0.0 <= float(data["risk_score"]) <= 1.0
