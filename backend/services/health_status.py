"""Dependency checks for operational health probes."""

from __future__ import annotations

from typing import Any

from ml.model_loader import get_model_status
from schemas.enums import HealthStatus, ModelLiveStatus
from services.history.firestore_io import get_firestore_client


def _check_status(ok: bool) -> str:
    return "ok" if ok else "unavailable"


def build_health_report() -> dict[str, Any]:
    """
    Aggregate readiness of production dependencies.

    Both Firestore and a live gated model are required for POST /predict/daily.
    """
    firestore_ok = get_firestore_client() is not None
    model_status = get_model_status()
    model_live = model_status.get("status") == ModelLiveStatus.LIVE.value

    checks: dict[str, Any] = {
        "firestore": {"status": _check_status(firestore_ok)},
        "ml_model": {
            "status": "live" if model_live else "blocked",
            "gate_reason": model_status.get("gate_reason"),
        },
    }

    healthy = firestore_ok and model_live
    return {
        "status": HealthStatus.HEALTHY.value if healthy else HealthStatus.UNHEALTHY.value,
        "checks": checks,
    }


def health_http_status_code(report: dict[str, Any]) -> int:
    """200 when all checks pass; 503 when a production dependency is down."""
    return 200 if report.get("status") == HealthStatus.HEALTHY.value else 503
