"""Integration tests for request logging middleware and observability routes."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from main import app

pytestmark = pytest.mark.integration


class TestRequestLoggingMiddleware:
    @pytest.fixture
    def client(self) -> TestClient:
        with TestClient(app) as test_client:
            yield test_client

    def test_health_is_not_logged_and_has_no_request_id_header(self, client, monkeypatch):
        captured: list[logging.LogRecord] = []

        def _capture(record: logging.LogRecord) -> bool:
            captured.append(record)
            return True

        from utils import logging as logging_module

        logging_module.logger.addFilter(_capture)
        try:
            response = client.get("/health")
        finally:
            logging_module.logger.removeFilter(_capture)

        # Logging middleware skips /health regardless of dependency readiness (200 or 503).
        assert response.status_code in (200, 503)
        assert "X-Request-ID" not in response.headers
        assert not any(getattr(r, "event", None) == "http_request_completed" for r in captured)

    def test_predict_daily_echoes_request_id_header(self, client, mock_daily_prediction_pipeline):
        mock_daily_prediction_pipeline()
        response = client.post(
            "/predict/daily",
            json={"userId": "trace-user", "date": "2026-06-20"},
            headers={"X-Request-ID": "trace-req-001"},
        )

        assert response.status_code == 200
        assert response.headers.get("X-Request-ID") == "trace-req-001"

    def test_predict_daily_generates_request_id_when_header_missing(self, client, mock_daily_prediction_pipeline):
        mock_daily_prediction_pipeline()
        response = client.post(
            "/predict/daily",
            json={"userId": "trace-user", "date": "2026-06-20"},
        )

        assert response.status_code == 200
        assert response.headers.get("X-Request-ID")


class TestClientEventsRoute:
    @pytest.fixture
    def client(self) -> TestClient:
        with TestClient(app) as test_client:
            yield test_client

    def test_client_events_returns_202_and_echoes_request_id(self, client):
        response = client.post(
            "/api/v1/observability/client-events",
            json={
                "event_type": "error",
                "level": "ERROR",
                "tag": "manual_test",
                "message": "simulated client error",
                "request_id": "test-manual-001",
                "user_id": "demo",
                "app_version": "1.0",
                "timestamp": "2026-06-20T10:00:00Z",
            },
            headers={"X-Request-ID": "test-manual-001"},
        )

        assert response.status_code == 202
        body = response.json()
        assert body["accepted"] is True
        assert body["request_id"] == "test-manual-001"

    def test_screen_view_can_be_rate_limited(self, client):
        from utils.client_event_limiter import reset_client_event_limiter

        reset_client_event_limiter()
        payload = {
            "event_type": "screen_view",
            "level": "INFO",
            "tag": "Dashboard",
            "message": "screen_opened",
            "user_id": "demo",
            "screen": "AthleteDashboardActivity",
        }
        first = client.post("/api/v1/observability/client-events", json=payload)
        second = client.post("/api/v1/observability/client-events", json=payload)

        assert first.json()["accepted"] is True
        assert second.json()["accepted"] is False
        assert second.json()["reason"] == "rate_limited"
