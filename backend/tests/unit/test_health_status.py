"""Unit tests for dependency health reporting."""

from __future__ import annotations

import pytest

from schemas.enums import HealthStatus, ModelLiveStatus
from services.health_status import build_health_report, health_http_status_code

pytestmark = pytest.mark.unit


def test_build_health_report_healthy_when_all_dependencies_up(monkeypatch):
    monkeypatch.setattr("services.health_status.get_firestore_client", lambda: object())
    monkeypatch.setattr(
        "services.health_status.get_model_status",
        lambda: {"status": ModelLiveStatus.LIVE.value, "gate_reason": "none"},
    )

    report = build_health_report()

    assert report["status"] == HealthStatus.HEALTHY.value
    assert report["checks"]["firestore"]["status"] == "ok"
    assert report["checks"]["ml_model"]["status"] == "live"
    assert health_http_status_code(report) == 200


def test_build_health_report_unhealthy_when_firestore_unavailable(monkeypatch):
    monkeypatch.setattr("services.health_status.get_firestore_client", lambda: None)
    monkeypatch.setattr(
        "services.health_status.get_model_status",
        lambda: {"status": ModelLiveStatus.LIVE.value, "gate_reason": "none"},
    )

    report = build_health_report()

    assert report["status"] == HealthStatus.UNHEALTHY.value
    assert report["checks"]["firestore"]["status"] == "unavailable"
    assert health_http_status_code(report) == 503


def test_build_health_report_unhealthy_when_model_blocked(monkeypatch):
    monkeypatch.setattr("services.health_status.get_firestore_client", lambda: object())
    monkeypatch.setattr(
        "services.health_status.get_model_status",
        lambda: {
            "status": ModelLiveStatus.BLOCKED.value,
            "gate_reason": "manifest_corrupted",
        },
    )

    report = build_health_report()

    assert report["status"] == HealthStatus.UNHEALTHY.value
    assert report["checks"]["ml_model"]["status"] == "blocked"
    assert report["checks"]["ml_model"]["gate_reason"] == "manifest_corrupted"
    assert health_http_status_code(report) == 503
