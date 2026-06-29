"""Unit tests for prediction_service pure helpers and orchestration."""

from __future__ import annotations

import pandas as pd
import pytest

from schemas.inference import InjuryPredictionRequest
from services import prediction_service as ps
from services.field_transforms import injured_yesterday_for_request
from services.model_features import DEFAULT_FEATURE_VALUES, MODEL_FEATURE_COLUMNS
from services.preprocessing import injury_request_to_model_dataframe
from utils.exceptions import DatabaseError, MLModelError


pytestmark = pytest.mark.unit


class TestResolveModelBundle:
    def test_returns_none_when_model_not_loaded(self):
        est, cols, thr, med, winner, status = ps.resolve_model_bundle(None)
        assert est is None
        assert status == "model_not_loaded"
        assert winner == "fallback_demo"

    def test_rejects_non_dict_bundle(self):
        est, *_rest, status = ps.resolve_model_bundle("not-a-dict")
        assert est is None
        assert status == "unsupported_model_format"

    def test_rejects_missing_estimator(self):
        bundle = {"feature_columns": ["age"], "threshold": 0.35}
        est, *_rest, status = ps.resolve_model_bundle(bundle)
        assert est is None
        assert status == "missing_estimator"

    def test_rejects_empty_feature_columns(self):
        bundle = {"estimator": object(), "feature_columns": [], "threshold": 0.35}
        est, *_rest, status = ps.resolve_model_bundle(bundle)
        assert est is None
        assert status == "missing_feature_columns"

    def test_rejects_invalid_threshold(self):
        bundle = {"estimator": object(), "feature_columns": ["age"], "threshold": "bad"}
        est, *_rest, status = ps.resolve_model_bundle(bundle)
        assert est is None
        assert status == "invalid_threshold"

    def test_derives_medium_threshold_when_absent(self, mock_model_bundle):
        del mock_model_bundle["medium_threshold"]
        mock_model_bundle["threshold"] = 0.40
        _est, _cols, thr, med, winner, status = ps.resolve_model_bundle(mock_model_bundle)
        assert status == "none"
        assert thr == pytest.approx(0.40)
        assert med == pytest.approx(max(0.15, 0.40 * 0.6))

    def test_valid_bundle_returns_all_fields(self, mock_model_bundle):
        est, cols, thr, med, winner, status = ps.resolve_model_bundle(mock_model_bundle)
        assert est is mock_model_bundle["estimator"]
        assert cols == MODEL_FEATURE_COLUMNS
        assert thr == pytest.approx(0.35)
        assert med == pytest.approx(0.20)
        assert winner == "ExtraTrees"
        assert status == "none"


class TestConfidenceScoring:
    @pytest.mark.parametrize(
        ("confidence", "expected"),
        [("high", 0.95), ("medium", 0.7), ("low", 0.45), ("unknown", 0.45)],
    )
    def test_history_score_from_confidence(self, confidence, expected):
        assert ps._history_score_from_confidence(confidence) == pytest.approx(expected)

    def test_prediction_confidence_blends_history_and_quality(self):
        # 0.6 * 0.95 + 0.4 * 0.8 = 0.89 → 89.0
        score = ps._prediction_confidence_0_100("high", 0.8)
        assert score == pytest.approx(89.0)

    def test_prediction_confidence_clamped_to_0_100(self):
        assert ps._prediction_confidence_0_100("low", 0.0) == pytest.approx(27.0)
        assert ps._prediction_confidence_0_100("high", 1.0) == pytest.approx(97.0)


class TestDefaultedCriticalFeatures:
    def test_counts_columns_matching_defaults(self):
        df = injury_request_to_model_dataframe(
            InjuryPredictionRequest(userId="u1", date="2026-04-30", sleepMinutes=420, steps=5000)
        )
        count = ps._count_defaulted_critical_features(df)
        assert count >= 0
        assert count <= 6

    def test_counts_zero_when_history_features_differ(self):
        df = pd.DataFrame([dict(DEFAULT_FEATURE_VALUES)], columns=MODEL_FEATURE_COLUMNS)
        df.at[df.index[0], "acwr_ratio"] = 1.85
        df.at[df.index[0], "hrv_drop"] = -3.2
        count = ps._count_defaulted_critical_features(df)
        assert count == 4  # only acwr_ratio and hrv_drop differ from defaults


class TestFirestoreFieldHelpers:
    def test_injured_yesterday_for_request_bool_and_int(self):
        assert injured_yesterday_for_request(True) == 1
        assert injured_yesterday_for_request(False) == 0
        assert injured_yesterday_for_request(1) == 1
        assert injured_yesterday_for_request(None) is None
        assert injured_yesterday_for_request("bad") is None

    def test_firestore_doc_heartrate_avg_prefers_heart_rate_avg(self):
        assert ps._firestore_doc_heartrate_avg({"heartRateAvg": 58, "avgHeartRate": 62}) == 58

    def test_firestore_doc_heartrate_avg_falls_back_to_avg_heart_rate(self):
        assert ps._firestore_doc_heartrate_avg({"avgHeartRate": 62}) == 62

    def test_field_from_docs_prefers_primary_non_zero(self):
        primary = {"steps": 0, "distanceMeters": 5000}
        fallback = {"steps": 9000}
        val = ps._field_from_docs(
            primary, fallback, ["steps", "distanceMeters"], prefer_primary=True
        )
        assert val == 5000

    def test_field_from_docs_falls_back_when_primary_missing(self):
        primary = {}
        fallback = {"steps": 7400}
        val = ps._field_from_docs(primary, fallback, ["steps"], prefer_primary=True)
        assert val == 7400


class TestFirestoreSnapshotMapping:
    def test_merge_policy_sleep_today_load_yesterday(self, firestore_snapshot):
        req = ps.injury_prediction_request_from_firestore_snapshot(
            "u1", "2026-06-16", firestore_snapshot
        )
        assert req.sleepMinutes == 480
        assert req.steps == 8300
        assert req.distanceMeters == 7200
        assert req.heartRateAvg == 58
        assert req.age == 31
        assert req.historyInjuryCount == 2
        assert req.totalProtein == 130
        assert req.nutritionTotalCalories == 2550

    def test_age_from_birth_date_in_profile(self, firestore_snapshot):
        snap = dict(firestore_snapshot)
        snap["profile"] = {"birth_date": "1995-01-01", "historyInjuryCount": 2}
        req = ps.injury_prediction_request_from_firestore_snapshot("u1", "2026-06-16", snap)
        assert req.age == 31

    def test_injured_yesterday_from_checkins(self, firestore_snapshot):
        snap = dict(firestore_snapshot)
        snap["daily_checkins"] = dict(snap["daily_checkins"], injuredYesterday=1)
        req = ps.injury_prediction_request_from_firestore_snapshot("u1", "2026-06-16", snap)
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
        req = ps.injury_prediction_request_from_firestore_snapshot("u1", "2026-06-16", snap)
        assert req.sleepMinutes == 480
        assert req.steps == 0
        assert req.distanceMeters == 0
        assert req.heartRateAvg is None

    def test_nutrition_imputed_when_yesterday_meals_missing(self, firestore_snapshot):
        snap = dict(firestore_snapshot)
        snap["daily_nutrition_yesterday"] = {}
        req = ps.injury_prediction_request_from_firestore_snapshot("u1", "2026-06-16", snap)
        assert req.nutritionImputed is True
        assert req.totalProtein == 130

    def test_nutrition_not_imputed_when_yesterday_logged(self, firestore_snapshot):
        req = ps.injury_prediction_request_from_firestore_snapshot("u1", "2026-06-16", firestore_snapshot)
        assert req.nutritionImputed is False


class TestPredictInjuryRisk:
    def test_raises_when_model_blocked(self, sample_prediction_request, monkeypatch):
        monkeypatch.setattr(ps, "get_model", lambda: None)
        monkeypatch.setattr(ps, "get_model_gate_reason", lambda: "manifest_corrupted")
        with pytest.raises(MLModelError, match="Model is not live: manifest_corrupted"):
            ps.predict_injury_risk(sample_prediction_request)

    @pytest.mark.parametrize(
        ("probability", "expected_level"),
        [
            (0.75, "High"),
            (0.71, "High"),
            (0.70, "Medium"),
            (0.50, "Medium"),
            (0.21, "Medium"),
            (0.20, "Low"),
            (0.15, "Low"),
        ],
    )
    def test_risk_level_cutoffs(
        self,
        sample_prediction_request,
        mock_model_bundle,
        monkeypatch,
        probability,
        expected_level,
    ):
        class _Estimator:
            feature_names_in_ = MODEL_FEATURE_COLUMNS

            def __init__(self, prob: float):
                self._prob = prob

            def predict_proba(self, X):
                import numpy as np

                return np.array([[1.0 - self._prob, self._prob]])

        bundle = dict(mock_model_bundle)
        bundle["estimator"] = _Estimator(probability)
        def _history_context(
            user_id: str,
            date_key: str,
            lookback_days: int | None = None,
            include_target_day: bool = True,
        ) -> dict[str, object]:
            return {"confidence": "medium", "features": {}}

        monkeypatch.setattr(ps, "get_model", lambda: bundle)
        monkeypatch.setattr(ps, "get_history_window_context", _history_context)
        out = ps.predict_injury_risk(sample_prediction_request)
        assert out["risk_level"] == expected_level
        assert out["risk_score"] == pytest.approx(probability, abs=1e-4)


    def test_from_firestore_raises_when_snapshot_empty(self, monkeypatch):
        monkeypatch.setattr(ps, "fetch_daily_firestore_snapshot", lambda uid, d: {})
        with pytest.raises(DatabaseError, match="Firestore snapshot unavailable"):
            ps.predict_injury_risk_from_firestore("u1", "2026-05-09")

    def test_persist_raises_on_write_failure(self, monkeypatch):
        def _save_failed(user_id: str, date_key: str, result: dict) -> bool:
            return False

        monkeypatch.setattr(ps, "save_daily_prediction_result", _save_failed)
        with pytest.raises(DatabaseError, match="Prediction persist failed"):
            ps.persist_prediction_result_or_raise("u1", "2026-05-09", {"risk_score": 0.3})
