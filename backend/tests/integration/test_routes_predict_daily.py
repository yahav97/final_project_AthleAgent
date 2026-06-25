"""Integration tests for POST /predict/daily — production inference contract."""

import pytest

from utils.exceptions import DatabaseError

pytestmark = pytest.mark.integration

DAILY_TRIGGER = {"userId": "test-athlete-001", "date": "2026-05-09"}


class TestPredictDailyValidation:
    @pytest.mark.parametrize(
        "payload,missing_field",
        [
            ({"date": "2026-05-09"}, "userId"),
            ({"userId": "u1"}, "date"),
            ({}, "userId"),
        ],
    )
    def test_missing_required_field_returns_422(self, api_client, payload, missing_field):
        response = api_client.post("/predict/daily", json=payload)

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert any(missing_field in str(item.get("loc", "")) for item in detail)

    def test_invalid_json_body_returns_422(self, api_client):
        response = api_client.post(
            "/predict/daily",
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_empty_user_id_still_accepted_by_schema(self, api_client, mock_daily_prediction_pipeline):
        mock_daily_prediction_pipeline()
        response = api_client.post("/predict/daily", json={"userId": "", "date": "2026-05-09"})
        assert response.status_code == 200


class TestPredictDailySuccess:
    def test_minimal_trigger_returns_production_response_shape(
        self, api_client, mock_daily_prediction_pipeline
    ):
        mock_daily_prediction_pipeline()
        response = api_client.post("/predict/daily", json=DAILY_TRIGGER)

        assert response.status_code == 200
        data = response.json()
        assert set(data.keys()) == {"risk_level", "risk_score", "prediction_confidence"}
        assert data["risk_level"] in ("Low", "Medium", "High")
        assert 0.0 <= float(data["risk_score"]) <= 1.0
        assert 0.0 <= float(data["prediction_confidence"]) <= 100.0

    def test_success_persists_prediction_before_response(
        self, api_client, mock_daily_prediction_pipeline
    ):
        called = mock_daily_prediction_pipeline(
            prediction_result={
                "risk_level": "High",
                "risk_score": 0.88,
                "prediction_confidence": 91.0,
            }
        )
        response = api_client.post("/predict/daily", json={"userId": "u1", "date": "2026-04-30"})

        assert response.status_code == 200
        data = response.json()
        assert data["risk_level"] == "High"
        assert abs(float(data["risk_score"]) - 0.88) < 1e-9
        assert called["predicted"] is True
        assert called["persisted"] is True

    def test_response_matches_injury_prediction_response_schema(
        self, api_client, mock_daily_prediction_pipeline
    ):
        mock_daily_prediction_pipeline()
        response = api_client.post("/predict/daily", json=DAILY_TRIGGER)
        assert response.status_code == 200
        assert response.json()["prediction_confidence"] == pytest.approx(72.5)


class TestPredictDailyErrors:
    def test_prediction_failure_returns_503_with_detail(
        self, api_client, mock_daily_prediction_pipeline
    ):
        mock_daily_prediction_pipeline(
            predict_raises=DatabaseError("Firestore request timed out", code="firestore_timeout")
        )
        response = api_client.post("/predict/daily", json=DAILY_TRIGGER)

        assert response.status_code == 503
        data = response.json()
        assert "Firestore request timed out" in data["detail"]
        assert data["code"] == "firestore_timeout"

    def test_persist_failure_returns_503(self, api_client, mock_daily_prediction_pipeline):
        mock_daily_prediction_pipeline(
            persist_raises=DatabaseError("Firestore write failed", code="write_failed")
        )
        response = api_client.post("/predict/daily", json=DAILY_TRIGGER)

        assert response.status_code == 503
        data = response.json()
        assert "Firestore write failed" in data["detail"]
        assert data["code"] == "write_failed"

    def test_model_gate_blocks_inference(
        self,
        api_client,
        mock_firestore_snapshot,
        mock_model_gate,
        monkeypatch,
    ):
        from api.routes import predict as predict_routes

        mock_firestore_snapshot()
        mock_model_gate(live=False, gate_reason="manifest_corrupted")
        def _persist_noop(user_id: str, date_key: str, result: dict) -> None:
            return None

        monkeypatch.setattr(predict_routes, "persist_prediction_result_or_raise", _persist_noop)

        response = api_client.post("/predict/daily", json={"userId": "u1", "date": "2026-04-30"})

        assert response.status_code == 503
        data = response.json()
        assert "Model is not live" in data["detail"]
        assert data["code"] == "model_not_live:manifest_corrupted"
