"""Integration tests for GET /status/ml operational endpoint."""

import pytest

pytestmark = pytest.mark.integration

ML_STATUS_KEYS = {"status", "gate_reason", "winner", "threshold", "policy", "degraded_rc"}


class TestMlStatusRoute:
    def test_get_status_returns_expected_schema(self, api_client):
        response = api_client.get("/status/ml")

        assert response.status_code == 200
        data = response.json()
        assert set(data.keys()) == ML_STATUS_KEYS
        assert data["status"] in ("Live", "Blocked")
        assert isinstance(data["gate_reason"], str)
        assert isinstance(data["policy"], dict)
        assert isinstance(data["degraded_rc"], bool)

    def test_get_status_is_read_only_and_idempotent(self, api_client):
        snapshots = [api_client.get("/status/ml").json() for _ in range(5)]
        assert all(set(item.keys()) == ML_STATUS_KEYS for item in snapshots)
        assert snapshots[0]["status"] == snapshots[-1]["status"]

    def test_get_status_does_not_mutate_on_post(self, api_client):
        before = api_client.get("/status/ml").json()
        api_client.post("/status/ml", json={})
        after = api_client.get("/status/ml").json()
        assert before["status"] == after["status"]
