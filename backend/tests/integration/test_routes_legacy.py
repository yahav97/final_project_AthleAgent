"""Integration tests for legacy/demo prediction routes."""

import pytest

from config import settings

pytestmark = pytest.mark.integration

def _legacy_athlete_payload(overrides: dict[str, float | int] | None = None) -> dict[str, float | int]:
    """Full AthleteData body with optional field overrides for heuristic tests."""
    payload: dict[str, float | int] = {
        "bmi": 22.1,
        "age": 28,
        "history_injury_count": 0,
        "injured_yesterday": 0,
        "daily_distance_km": 4.0,
        "workout_intensity_minutes": 40,
        "avg_cadence": 165,
        "sleep_hours": 7.0,
        "hrv_score": 62,
        "resting_hr": 54,
        "nutrition_intake_calories": 2500,
        "daily_calories": 2400,
        "total_calories_burned": 2500,
        "calorie_balance": -100,
        "stress_level": 4,
        "muscle_soreness": 3,
        "energy_level": 5,
        "acute_load_7d": 4.5,
        "chronic_load_21d": 5.0,
        "acwr_ratio": 0.9,
        "sleep_debt_3d": 1.0,
        "hrv_drop": -1.0,
    }
    if overrides:
        payload.update(overrides)
    return payload


_LEGACY_ATHLETE_PAYLOAD = _legacy_athlete_payload()


class TestTestPredictRoute:
    @pytest.fixture(autouse=True)
    def _enable_test_predict(self, monkeypatch):
        monkeypatch.setattr(settings, "ENABLE_TEST_PREDICT_ENDPOINT", True)

    def test_post_test_predict_returns_stable_mock(self, api_client):
        response = api_client.post("/test_predict", json={"user_id": "android-smoke-user"})

        assert response.status_code == 200
        assert response.json() == {
            "user_id": "android-smoke-user",
            "risk_percentage": settings.TEST_PREDICT_MOCK_RISK_PERCENTAGE,
            "risk_level": "High",
            "message": "This is a mock response for Android UI testing",
        }

    def test_post_test_predict_requires_user_id(self, api_client):
        response = api_client.post("/test_predict", json={})
        assert response.status_code == 422

    def test_post_test_predict_disabled_by_default(self, api_client, monkeypatch):
        monkeypatch.setattr(settings, "ENABLE_TEST_PREDICT_ENDPOINT", False)
        response = api_client.post("/test_predict", json={"user_id": "android-smoke-user"})
        assert response.status_code == 404


class TestSklearnLegacyRoute:
    def test_post_sklearn_disabled_by_default_returns_410(self, api_client):
        assert settings.ENABLE_LEGACY_SKLEARN_ENDPOINT is False
        response = api_client.post("/predict/sklearn", json=_LEGACY_ATHLETE_PAYLOAD)

        assert response.status_code == 410
        assert "Legacy endpoint disabled" in response.json()["detail"]

    def test_post_sklearn_when_enabled_without_model_returns_error_payload(
        self, api_client, monkeypatch
    ):
        monkeypatch.setattr(settings, "ENABLE_LEGACY_SKLEARN_ENDPOINT", True)
        monkeypatch.setattr(
            "api.routes.predict.get_model",
            lambda: None,
        )
        response = api_client.post("/predict/sklearn", json=_LEGACY_ATHLETE_PAYLOAD)

        assert response.status_code == 200
        assert response.json() == {"error": "Model not loaded"}
