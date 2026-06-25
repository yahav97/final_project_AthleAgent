"""Integration tests for demo prediction routes."""

import pytest

from config import settings

pytestmark = pytest.mark.integration


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
