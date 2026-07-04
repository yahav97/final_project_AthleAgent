"""Unit tests for prediction orchestration and Firestore mapping."""

from __future__ import annotations

import pandas as pd
import pytest

from schemas.inference import InjuryPredictionRequest
from services.model_features import DEFAULT_FEATURE_VALUES, MODEL_FEATURE_COLUMNS
from services.prediction.bundle import resolve_model_bundle
from services.prediction.confidence import count_defaulted_critical_features
from services.nutrition_defaults import resolve_request_nutrition
from services.prediction.firestore_mapping import injury_prediction_request_from_firestore_snapshot
from services.field_transforms import heart_rate_avg_from_doc
from services.prediction.service import (
    persist_prediction_result_or_raise,
    predict_injury_risk,
    predict_injury_risk_from_firestore,
)
from services.preprocessing import injury_request_to_model_dataframe
from utils.exceptions import DatabaseError, MLModelError


pytestmark = pytest.mark.unit


class TestResolveModelBundle:
    def test_returns_none_when_model_not_loaded(self):
        bundle = resolve_model_bundle(None)
        assert bundle.estimator is None
        assert bundle.gate_status == "model_not_loaded"
        assert bundle.model_name == "fallback_demo"

    def test_rejects_non_dict_bundle(self):
        bundle = resolve_model_bundle("not-a-dict")
        assert bundle.estimator is None
        assert bundle.gate_status == "unsupported_model_format"

    def test_rejects_missing_estimator(self):
        payload = {"feature_columns": ["age"], "threshold": 0.35}
        bundle = resolve_model_bundle(payload)
        assert bundle.estimator is None
        assert bundle.gate_status == "missing_estimator"

    def test_rejects_empty_feature_columns(self):
        payload = {"estimator": object(), "feature_columns": [], "threshold": 0.35}
        bundle = resolve_model_bundle(payload)
        assert bundle.estimator is None
        assert bundle.gate_status == "missing_feature_columns"

    def test_rejects_invalid_threshold(self):
        payload = {"estimator": object(), "feature_columns": ["age"], "threshold": "bad"}
        bundle = resolve_model_bundle(payload)
        assert bundle.estimator is None
        assert bundle.gate_status == "invalid_threshold"

    def test_derives_medium_threshold_when_absent(self, mock_model_bundle):
        del mock_model_bundle["medium_threshold"]
        mock_model_bundle["threshold"] = 0.40
        bundle = resolve_model_bundle(mock_model_bundle)
        assert bundle.gate_status == "none"
        assert bundle.injury_threshold == pytest.approx(0.40)
        assert bundle.medium_risk_threshold == pytest.approx(max(0.15, 0.40 * 0.6))

    def test_valid_bundle_returns_all_fields(self, mock_model_bundle):
        bundle = resolve_model_bundle(mock_model_bundle)
        assert bundle.estimator is mock_model_bundle["estimator"]
        assert bundle.feature_columns == MODEL_FEATURE_COLUMNS
        assert bundle.injury_threshold == pytest.approx(0.35)
        assert bundle.medium_risk_threshold == pytest.approx(0.20)
        assert bundle.model_name == "ExtraTrees"
        assert bundle.gate_status == "none"


class TestDefaultedCriticalFeatures:
    def test_counts_defaults_for_same_day_proxy_features(self):
        df = injury_request_to_model_dataframe(
            InjuryPredictionRequest(
                userId="u1",
                date="2026-04-30",
                age=28,
                sleepMinutes=420,
                steps=5000,
                stressLevel=40,
                muscleSoreness=3,
                energyLevel=70,
            )
        )
        count = count_defaulted_critical_features(df)
        # sleep_hours_ma7 and hrv_drop match population defaults; others come from same-day load.
        assert count == 2

    def test_counts_all_six_when_frame_uses_population_defaults(self):
        df = pd.DataFrame([dict(DEFAULT_FEATURE_VALUES)], columns=MODEL_FEATURE_COLUMNS)
        assert count_defaulted_critical_features(df) == 6

    def test_counts_zero_when_history_features_differ(self):
        df = pd.DataFrame([dict(DEFAULT_FEATURE_VALUES)], columns=MODEL_FEATURE_COLUMNS)
        df.at[df.index[0], "acwr_ratio"] = 1.85
        df.at[df.index[0], "hrv_drop"] = -3.2
        count = count_defaulted_critical_features(df)
        assert count == 4  # only acwr_ratio and hrv_drop differ from defaults


class TestFirestoreFieldHelpers:
    def test_heart_rate_avg_reads_canonical_field(self):
        assert heart_rate_avg_from_doc({"heartRateAvg": 58}) == 58

    def test_heart_rate_avg_missing_returns_none(self):
        assert heart_rate_avg_from_doc({}) is None


class TestFirestoreSnapshotMapping:
    def test_merge_policy_sleep_today_load_yesterday(self, firestore_snapshot):
        req = injury_prediction_request_from_firestore_snapshot(
            "u1", "2026-06-16", firestore_snapshot
        )
        assert req.sleepMinutes == 480
        assert req.steps == 8300
        assert req.distanceMeters == 7200
        assert req.heartRateAvg == 58
        assert req.age == 31.48
        assert req.historyInjuryCount == 2
        assert req.totalProtein == 130
        assert req.nutritionTotalCalories == 2550

    def test_age_from_birth_date_in_profile(self, firestore_snapshot):
        snap = dict(firestore_snapshot)
        snap["profile"] = {"birth_date": "1995-01-01", "historyInjuryCount": 2}
        req = injury_prediction_request_from_firestore_snapshot("u1", "2026-06-16", snap)
        assert req.age == 31.48

    def test_missing_birth_date_in_profile_leaves_age_none(self, firestore_snapshot):
        snap = dict(firestore_snapshot)
        snap["profile"] = {"historyInjuryCount": 2}
        req = injury_prediction_request_from_firestore_snapshot("u1", "2026-06-16", snap)
        assert req.age is None

    def test_injured_yesterday_from_checkins(self, firestore_snapshot):
        snap = dict(firestore_snapshot)
        snap["daily_checkins"] = dict(snap["daily_checkins"], injuredYesterday=1)
        req = injury_prediction_request_from_firestore_snapshot("u1", "2026-06-16", snap)
        assert req.injuredYesterday == 1

    def test_physical_load_ignores_today_doc(self, firestore_snapshot):
        snap = dict(firestore_snapshot)
        snap["daily_health_yesterday"] = {}
        snap["daily_health"] = {
            "sleepMinutes": 480,
            "steps": 5000,
            "distanceMeters": 4000,
            "heartRateAvg": 72,
        }
        req = injury_prediction_request_from_firestore_snapshot("u1", "2026-06-16", snap)
        assert req.sleepMinutes == 480
        assert req.steps == 0
        assert req.distanceMeters == 0
        assert req.heartRateAvg is None

    def test_missing_birth_date_flags_age_imputed(self, firestore_snapshot):
        from services.profile_defaults import resolve_request_age

        snap = dict(firestore_snapshot)
        snap["profile"] = {"historyInjuryCount": 2}
        mapped = injury_prediction_request_from_firestore_snapshot("u1", "2026-06-16", snap)
        assert mapped.age is None
        req = resolve_request_age(mapped)
        assert req.ageImputed is True

    def test_nutrition_imputed_when_yesterday_meals_missing(self, firestore_snapshot):
        snap = dict(firestore_snapshot)
        snap["daily_nutrition_yesterday"] = {}
        mapped = injury_prediction_request_from_firestore_snapshot("u1", "2026-06-16", snap)
        req = resolve_request_nutrition(mapped)
        assert req.nutritionImputed is True
        assert req.totalProtein == 130

    def test_nutrition_not_imputed_when_yesterday_logged(self, firestore_snapshot):
        mapped = injury_prediction_request_from_firestore_snapshot("u1", "2026-06-16", firestore_snapshot)
        req = resolve_request_nutrition(mapped)
        assert req.nutritionImputed is False


class TestPredictInjuryRisk:
    def test_missing_age_uses_profile_default(
        self,
        sample_prediction_request,
        mock_model_bundle,
        monkeypatch,
    ):
        class _Estimator:
            feature_names_in_ = MODEL_FEATURE_COLUMNS

            def predict_proba(self, X):
                import numpy as np

                assert float(X["age"].iloc[0]) == pytest.approx(22.0)
                return np.array([[0.35, 0.65]])

        bundle = dict(mock_model_bundle)
        bundle["estimator"] = _Estimator()
        payload = InjuryPredictionRequest(
            userId="u1",
            date="2026-04-30",
            sleepMinutes=420,
            steps=5000,
            stressLevel=40,
            muscleSoreness=3,
            energyLevel=70,
            ageImputed=True,
        )

        monkeypatch.setattr("services.prediction.service.get_model", lambda: bundle)
        monkeypatch.setattr(
            "services.prediction.confidence.get_history_window_context",
            lambda *a, **k: {"confidence": "low", "features": {}},
        )
        out = predict_injury_risk(payload)
        assert out["risk_level"] == "Medium"
        assert 0.0 <= out["prediction_confidence"] <= 100.0

    def test_raises_when_model_blocked(self, sample_prediction_request, monkeypatch):
        monkeypatch.setattr("services.prediction.service.get_model", lambda: None)
        monkeypatch.setattr(
            "services.prediction.service.get_model_gate_reason",
            lambda: "manifest_corrupted",
        )
        with pytest.raises(MLModelError, match="Model is not live: manifest_corrupted"):
            predict_injury_risk(sample_prediction_request)

    def test_response_includes_classified_risk_level(
        self,
        sample_prediction_request,
        mock_model_bundle,
        monkeypatch,
    ):
        class _Estimator:
            feature_names_in_ = MODEL_FEATURE_COLUMNS

            def predict_proba(self, X):
                import numpy as np

                return np.array([[0.35, 0.65]])

        bundle = dict(mock_model_bundle)
        bundle["estimator"] = _Estimator()

        monkeypatch.setattr("services.prediction.service.get_model", lambda: bundle)
        monkeypatch.setattr(
            "services.prediction.confidence.get_history_window_context",
            lambda *a, **k: {"confidence": "medium", "features": {}},
        )
        out = predict_injury_risk(sample_prediction_request)
        assert out["risk_level"] == "Medium"
        assert out["risk_score"] == pytest.approx(0.65, abs=1e-4)
        assert 0.0 <= out["prediction_confidence"] <= 100.0

    def test_history_enrichment_affects_risk_score(
        self,
        sample_prediction_request,
        mock_model_bundle,
        monkeypatch,
    ):
        import numpy as np

        class _FeatureSensitiveEstimator:
            feature_names_in_ = MODEL_FEATURE_COLUMNS

            def predict_proba(self, X):
                acwr = float(X["acwr_ratio"].iloc[0])
                prob = min(0.95, max(0.05, 0.15 + acwr * 0.2))
                return np.array([[1.0 - prob, prob]])

        bundle = dict(mock_model_bundle)
        bundle["estimator"] = _FeatureSensitiveEstimator()

        def _low_history(*args, **kwargs):
            return {"confidence": "low", "features": {}}

        def _high_history(*args, **kwargs):
            return {
                "confidence": "high",
                "features": {"acwr_ratio": 2.5, "acwr_ratio_ma7": 2.5},
            }

        monkeypatch.setattr("services.prediction.service.get_model", lambda: bundle)
        monkeypatch.setattr(
            "services.prediction.confidence.get_history_window_context",
            _low_history,
        )
        low_out = predict_injury_risk(sample_prediction_request)

        monkeypatch.setattr(
            "services.prediction.confidence.get_history_window_context",
            _high_history,
        )
        high_out = predict_injury_risk(sample_prediction_request)

        assert high_out["risk_score"] > low_out["risk_score"]
        assert high_out["prediction_confidence"] > low_out["prediction_confidence"]

    def test_from_firestore_raises_when_snapshot_empty(self, monkeypatch):
        monkeypatch.setattr(
            "services.prediction.service.fetch_daily_firestore_snapshot",
            lambda uid, d: {},
        )
        with pytest.raises(DatabaseError, match="Firestore snapshot unavailable"):
            predict_injury_risk_from_firestore("u1", "2026-05-09")

    def test_persist_raises_on_write_failure(self, monkeypatch):
        def _save_failed(user_id: str, date_key: str, result: dict) -> bool:
            return False

        monkeypatch.setattr(
            "services.prediction.service.save_daily_prediction_result",
            _save_failed,
        )
        with pytest.raises(DatabaseError, match="Prediction persist failed"):
            persist_prediction_result_or_raise("u1", "2026-05-09", {"risk_score": 0.3})
