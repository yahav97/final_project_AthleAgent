"""Unit and integration tests for request logging middleware and correlation IDs."""

from __future__ import annotations

import json
import logging
from io import StringIO

import pytest
from fastapi.testclient import TestClient

from main import app
from utils.logging import setup_logging
from utils.request_context import get_or_create_request_id, request_id_var, user_id_var

pytestmark = pytest.mark.unit


class TestRequestContext:
    def test_get_or_create_request_id_uses_client_value(self):
        rid = get_or_create_request_id("client-abc-123")
        assert rid == "client-abc-123"
        assert request_id_var.get() == "client-abc-123"

    def test_get_or_create_request_id_generates_uuid_when_missing(self):
        rid = get_or_create_request_id(None)
        assert rid
        assert len(rid) == 36


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

        assert response.status_code == 200
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


class TestJsonLogging:
    def test_json_formatter_emits_parseable_line(self, tmp_path):
        from utils.logging import ContextFilter

        stream = StringIO()
        root = setup_logging(log_dir=tmp_path, level="INFO", log_format="json")
        handler = logging.StreamHandler(stream)
        from pythonjsonlogger.json import JsonFormatter

        handler.setFormatter(
            JsonFormatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s",
                rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
            )
        )
        handler.addFilter(ContextFilter())
        root.handlers.clear()
        root.addHandler(handler)

        request_id_var.set("json-test-id")
        user_id_var.set("user-1")
        root.info("structured_event", extra={"event": "structured_event"})

        payload = json.loads(stream.getvalue().strip())
        assert payload["message"] == "structured_event"
        assert payload["event"] == "structured_event"
        assert payload["request_id"] == "json-test-id"
        assert payload["user_id"] == "user-1"
        assert payload["source"] == "backend"
