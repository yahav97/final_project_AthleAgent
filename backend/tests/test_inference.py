"""HTTP contract tests for injury inference."""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_predict_production_contract():
    sample = {
        "userId": "test_uid",
        "date": "2026-04-19",
        "sleepMinutes": 480,
        "steps": 8200,
        "distanceMeters": 6400,
        "energyLevel": 4,
        "muscleSoreness": 2,
        "stressLevel": 35,
        "totalCalories": 2400,
        "totalProtein": 120,
        "totalCarbs": 280,
        "mealsLoggedCount": 3,
    }
    response = client.post("/predict", json=sample)
    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == {"risk_level", "risk_score", "recommendation"}
    assert data["risk_level"] in ("Low", "Medium", "High")
    assert isinstance(data["risk_score"], (int, float))
    assert 0.0 <= float(data["risk_score"]) <= 1.0
    assert len(data["recommendation"]) > 5
