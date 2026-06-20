"""Integration tests for root and liveness routes."""

import pytest

from config import settings

pytestmark = pytest.mark.integration


class TestRootRoute:
    def test_get_root_returns_service_metadata(self, api_client):
        response = api_client.get("/")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        body = response.json()
        assert body == {
            "status": "ok",
            "service": settings.PROJECT_NAME,
            "version": settings.VERSION,
        }

    def test_get_root_is_idempotent(self, api_client):
        first = api_client.get("/").json()
        second = api_client.get("/").json()
        assert first == second


class TestHealthRoute:
    def test_get_health_returns_healthy(self, api_client):
        response = api_client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_get_health_does_not_require_auth(self, api_client):
        response = api_client.get("/health", headers={})
        assert response.status_code == 200
