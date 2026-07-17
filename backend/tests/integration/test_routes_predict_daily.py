"""Integration tests for POST /predict/daily — production inference contract."""

from typing import Any

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

    def test_invalid_calendar_date_returns_422(self, api_client):
        response = api_client.post(
            "/predict/daily",
            json={"userId": "u1", "date": "2026-02-30"},
        )
        assert response.status_code == 422


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

    def test_persist_failure_still_returns_prediction(self, api_client, monkeypatch):
        from services.prediction import service as prediction_service

        monkeypatch.setattr(
            prediction_service,
            "load_cached_daily_prediction",
            lambda uid, d: None,
        )
        monkeypatch.setattr(
            prediction_service,
            "predict_injury_risk_from_firestore",
            lambda uid, d: {
                "risk_level": "Medium",
                "risk_score": 0.42,
                "prediction_confidence": 72.5,
            },
        )
        monkeypatch.setattr(
            prediction_service,
            "save_daily_prediction_result_with_retries",
            lambda uid, d, r, **kw: False,
        )

        response = api_client.post("/predict/daily", json=DAILY_TRIGGER)

        assert response.status_code == 200
        data = response.json()
        assert data["risk_level"] == "Medium"
        assert abs(float(data["risk_score"]) - 0.42) < 1e-9
        assert float(data["prediction_confidence"]) == pytest.approx(72.5)

    def test_idempotent_retry_returns_cached_prediction_without_re_inference(
        self, api_client, monkeypatch
    ):
        from services.prediction import service as prediction_service

        infer_calls = {"count": 0}

        def _infer(uid: str, d: str) -> dict[str, Any]:
            infer_calls["count"] += 1
            return {
                "risk_level": "Low",
                "risk_score": 0.12,
                "prediction_confidence": 80.0,
            }

        cached = {
            "risk_level": "High",
            "risk_score": 0.88,
            "prediction_confidence": 91.0,
        }
        monkeypatch.setattr(
            prediction_service,
            "load_cached_daily_prediction",
            lambda uid, d: dict(cached),
        )
        monkeypatch.setattr(prediction_service, "predict_injury_risk_from_firestore", _infer)
        monkeypatch.setattr(
            prediction_service,
            "save_daily_prediction_result_with_retries",
            lambda uid, d, r, **kw: True,
        )

        response = api_client.post("/predict/daily", json=DAILY_TRIGGER)

        assert response.status_code == 200
        data = response.json()
        assert data["risk_level"] == "High"
        assert infer_calls["count"] == 0

    def test_model_gate_blocks_inference(
        self,
        api_client,
        mock_firestore_snapshot,
        mock_model_gate,
        monkeypatch,
    ):
        from api.routes import predict as predict_routes

        from utils.exceptions import MLModelError

        mock_firestore_snapshot()
        mock_model_gate(live=False, gate_reason="manifest_corrupted")

        def _blocked(uid: str, d: str) -> dict[str, Any]:
            raise MLModelError(
                "Model is not live: manifest_corrupted",
                code="model_not_live:manifest_corrupted",
            )

        monkeypatch.setattr(predict_routes, "run_daily_prediction", _blocked)

        response = api_client.post("/predict/daily", json={"userId": "u1", "date": "2026-04-30"})

        assert response.status_code == 503
        data = response.json()
        assert "Model is not live" in data["detail"]
        assert data["code"] == "model_not_live:manifest_corrupted"

    def test_missing_birth_date_still_predicts_through_http(
        self,
        api_client,
        mock_model_bundle,
        monkeypatch,
    ):
        from api.routes import predict as predict_routes

        snapshot_without_age = {
            "profile": {},
            "daily_health": {"sleepMinutes": 480},
            "daily_health_yesterday": {
                "steps": 8300,
                "distanceMeters": 7200,
                "heartRateAvg": 58,
            },
            "daily_checkins": {
                "muscleSoreness": 3,
                "stressLevel": 35,
                "energyLevel": 60,
            },
            "daily_nutrition_yesterday": {"totalCalories": 2400},
        }
        monkeypatch.setattr(
            "services.prediction.service.fetch_inference_firestore_bundle",
            lambda uid, d, **kwargs: {
                "snapshot": dict(snapshot_without_age),
                "history_context": {"confidence": "low", "features": {}},
            },
        )

        class _Estimator:
            feature_names_in_ = mock_model_bundle["feature_columns"]

            def predict_proba(self, X):
                import numpy as np

                return np.array([[0.35, 0.65]])

        bundle = dict(mock_model_bundle)
        bundle["estimator"] = _Estimator()
        monkeypatch.setattr("services.prediction.service.get_model", lambda: bundle)

        monkeypatch.setattr(
            "services.prediction.service.save_daily_prediction_result_with_retries",
            lambda uid, d, r, **kw: True,
        )

        response = api_client.post("/predict/daily", json=DAILY_TRIGGER)

        assert response.status_code == 200
        data = response.json()
        assert data["risk_level"] in ("Low", "Medium", "High")
        assert float(data["prediction_confidence"]) < 100.0
