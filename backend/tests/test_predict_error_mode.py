from fastapi.testclient import TestClient

from main import app


def test_predict_returns_500_when_model_gate_blocks(monkeypatch):
    from services import prediction_service as ps

    monkeypatch.setattr(ps, "get_model", lambda: None)
    monkeypatch.setattr(ps, "get_model_gate_reason", lambda: "manifest_corrupted")

    with TestClient(app) as client:
        response = client.post(
            "/predict",
            json={
                "userId": "u1",
                "date": "2026-04-30",
                "sleepMinutes": 450,
                "steps": 7400,
                "stressLevel": 33,
                "muscleSoreness": 3,
            },
        )
    assert response.status_code == 500
    body = response.json()
    assert "Prediction unavailable" in body["detail"]
