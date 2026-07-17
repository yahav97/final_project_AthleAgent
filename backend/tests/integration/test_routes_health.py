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


class TestHealthRoute:
    def test_get_health_includes_dependency_checks(self, api_client):
        response = api_client.get("/health")

        assert response.status_code in (200, 503)
        body = response.json()
        assert body["status"] in ("healthy", "unhealthy")
        assert "checks" in body
        assert body["checks"]["firestore"]["status"] in ("ok", "unavailable")
        assert body["checks"]["ml_model"]["status"] in ("live", "blocked")
        assert response.status_code == (200 if body["status"] == "healthy" else 503)
