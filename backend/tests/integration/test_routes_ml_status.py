"""Integration tests for GET /status/ml operational endpoint."""

import pytest

pytestmark = pytest.mark.integration

ML_STATUS_KEYS = {
    "status",
    "gate_reason",
    "winner",
    "threshold",
    "policy",
    "run_id",
    "promoted_at_utc",
    "manifest_path",
    "winner_metrics",
}


class TestMlStatusRoute:
    def test_get_status_returns_expected_schema(self, api_client):
        response = api_client.get("/status/ml")

        assert response.status_code == 200
        data = response.json()
        assert set(data.keys()) == ML_STATUS_KEYS
        assert data["status"] in ("Live", "Blocked")
        assert isinstance(data["gate_reason"], str)
        assert isinstance(data["policy"], dict)
        assert "winner_metrics" in data
        assert isinstance(data["winner_metrics"], dict)

    def test_get_status_reports_blocked_model(self, api_client, monkeypatch):
        monkeypatch.setattr(
            "api.routes.predict.get_model_status",
            lambda: {
                "status": "Blocked",
                "gate_reason": "manifest_corrupted",
                "winner": "ExtraTrees",
                "threshold": 0.35,
                "policy": {},
                "run_id": "run-test",
                "promoted_at_utc": "2026-01-01T00:00:00Z",
                "manifest_path": "/tmp/manifest.json",
                "winner_metrics": {},
            },
        )

        response = api_client.get("/status/ml")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Blocked"
        assert data["gate_reason"] == "manifest_corrupted"
