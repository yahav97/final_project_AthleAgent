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

    def test_get_health_returns_503_when_firestore_unavailable(self, api_client, monkeypatch):
        monkeypatch.setattr(
            "services.health_status.get_firestore_client",
            lambda: None,
        )
        monkeypatch.setattr(
            "services.health_status.get_model_status",
            lambda: {"status": "Live", "gate_reason": "none"},
        )

        response = api_client.get("/health")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "unhealthy"
        assert body["checks"]["firestore"]["status"] == "unavailable"

    def test_get_health_returns_503_when_model_blocked(self, api_client, monkeypatch):
        monkeypatch.setattr(
            "services.health_status.get_firestore_client",
            lambda: object(),
        )
        monkeypatch.setattr(
            "services.health_status.get_model_status",
            lambda: {"status": "Blocked", "gate_reason": "manifest_corrupted"},
        )

        response = api_client.get("/health")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "unhealthy"
        assert body["checks"]["ml_model"]["status"] == "blocked"
        assert body["checks"]["ml_model"]["gate_reason"] == "manifest_corrupted"
