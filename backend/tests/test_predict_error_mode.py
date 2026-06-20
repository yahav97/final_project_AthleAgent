from fastapi.testclient import TestClient

from api.routes import predict as predict_routes
from main import app
from services import prediction_service as ps


def test_predict_daily_returns_500_when_model_gate_blocks(monkeypatch):
    monkeypatch.setattr(
        ps,
        "fetch_daily_firestore_snapshot",
        lambda uid, d: {
            "profile": {},
            "daily_health": {"sleepMinutes": 450},
            "daily_health_yesterday": {"steps": 7400},
            "daily_checkins": {"stressLevel": 33, "muscleSoreness": 3},
            "daily_nutrition_yesterday": {},
        },
    )
    monkeypatch.setattr(ps, "get_model", lambda: None)
    monkeypatch.setattr(ps, "get_model_gate_reason", lambda: "manifest_corrupted")
    monkeypatch.setattr(predict_routes, "persist_prediction_result_or_raise", lambda *a, **k: None)

    with TestClient(app) as client:
        response = client.post(
            "/predict/daily",
            json={"userId": "u1", "date": "2026-04-30"},
        )
    assert response.status_code == 500
    body = response.json()
    assert "Prediction unavailable" in body["detail"]
