"""HTTP contract tests for injury inference."""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_predict_daily_production_contract():
    sample = {"userId": "test_uid", "date": "2026-04-19"}
    response = client.post("/predict/daily", json=sample)
    if response.status_code == 500:
        body = response.json()
        assert "Prediction unavailable" in body["detail"]
        return

    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == {
        "risk_level",
        "risk_score",
        "recommendation",
        "data_quality_score",
        "data_quality_status",
        "meta",
    }
    assert data["risk_level"] in ("Low", "Medium", "High")
    assert isinstance(data["risk_score"], (int, float))
    assert 0.0 <= float(data["risk_score"]) <= 1.0
    assert isinstance(data["data_quality_score"], (int, float))
    assert 0.0 <= float(data["data_quality_score"]) <= 1.0
    assert data["data_quality_status"] in ("Excellent", "Good", "Fair", "Poor")
    assert isinstance(data["meta"], dict)
    assert "model_version" in data["meta"]
    assert "fallback_reason" in data["meta"]
    assert "confidence_bucket" in data["meta"]
    assert data["meta"]["confidence_bucket"] in ("Low", "Medium", "High")
    assert len(data["recommendation"]) > 5


def test_predict_daily_minimal_trigger_contract(monkeypatch):
    from api.routes import predict as predict_routes

    called = {"persisted": False}

    monkeypatch.setattr(
        predict_routes,
        "predict_injury_risk_from_firestore",
        lambda user_id, date_key: {
            "risk_level": "Medium",
            "risk_score": 0.42,
            "recommendation": "Keep load stable today.",
            "data_quality_score": 0.81,
            "data_quality_status": "Good",
            "meta": {
                "model_version": "test_model",
                "fallback_reason": "none",
                "confidence_bucket": "Medium",
            },
        },
    )
    monkeypatch.setattr(
        predict_routes,
        "persist_prediction_result_or_raise",
        lambda user_id, date_key, result: called.__setitem__("persisted", True),
    )
    response = client.post("/predict/daily", json={"userId": "u1", "date": "2026-05-09"})
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] == "Medium"
    assert abs(float(data["risk_score"]) - 0.42) < 1e-9
    assert data["meta"]["model_version"] == "test_model"
    assert called["persisted"] is True


def test_predict_sklearn_legacy_endpoint_disabled_by_default():
    response = client.post(
        "/predict/sklearn",
        json={
            "age": 25,
            "bmi": 22.1,
            "history_injury_count": 0,
            "vo2_max": 50,
            "daily_distance_km": 4.0,
            "workout_intensity_minutes": 40,
            "avg_cadence": 165,
            "sleep_hours": 7.0,
            "hrv_score": 62,
            "resting_hr": 54,
            "daily_calories": 2400,
            "total_calories_burned": 2500,
            "calorie_balance": -100,
            "stress_level": 4,
            "muscle_soreness": 3,
            "acute_load_7d": 4.5,
            "chronic_load_21d": 5.0,
            "acwr_ratio": 0.9,
            "sleep_debt_3d": 1.0,
            "hrv_drop": -1.0,
        },
    )
    assert response.status_code == 410


def test_ml_status_endpoint_shape():
    response = client.get("/status/ml")
    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == {"status", "gate_reason", "winner", "threshold", "policy", "degraded_rc"}
    assert data["status"] in ("Live", "Blocked")
