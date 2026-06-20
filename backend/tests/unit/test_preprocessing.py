"""Unit tests for preprocessing scale mapping and feature validation."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from schemas.inference import InjuryPredictionRequest
from services.model_features import DEFAULT_FEATURE_VALUES, MODEL_FEATURE_COLUMNS
from services.preprocessing import (
    _energy_to_model_scale,
    _safe_float,
    _soreness_to_model_scale,
    _stress_to_model_scale,
    calculate_data_quality_score,
    injury_request_to_model_dataframe,
    validate_feature_vector_for_model,
)
from utils.exceptions import ValidationError

pytestmark = pytest.mark.unit


class TestScaleMapping:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [(None, DEFAULT_FEATURE_VALUES["stress_level"]), (80, 8.0), (5, 5.0), (150, 10.0)],
    )
    def test_stress_to_model_scale(self, raw, expected):
        assert _stress_to_model_scale(raw) == pytest.approx(expected)

    @pytest.mark.parametrize(
        ("raw", "expected_approx"),
        [(None, DEFAULT_FEATURE_VALUES["muscle_soreness"]), (3, 5.5), (5, 9.5)],
    )
    def test_soreness_to_model_scale(self, raw, expected_approx):
        assert _soreness_to_model_scale(raw) == pytest.approx(expected_approx)

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [(None, DEFAULT_FEATURE_VALUES["energy_level"]), (70, 7.0), (100, 10.0)],
    )
    def test_energy_to_model_scale(self, raw, expected):
        assert _energy_to_model_scale(raw) == pytest.approx(expected)


class TestSafeFloat:
    def test_converts_valid_numeric(self):
        assert _safe_float("42.5") == pytest.approx(42.5)

    def test_returns_fallback_on_invalid(self):
        assert _safe_float("not-a-number", fallback=7.0) == pytest.approx(7.0)

    def test_returns_fallback_on_non_finite(self):
        assert _safe_float(float("inf"), fallback=3.0) == pytest.approx(3.0)


class TestDataQualityScore:
    def test_full_payload_scores_high(self, sample_prediction_request):
        q = calculate_data_quality_score(sample_prediction_request)
        assert q["score"] == pytest.approx(1.0)
        assert q["has_hard_blocker"] is False
        assert q["hard_missing"] == []

    def test_missing_user_and_date_triggers_hard_blocker(self):
        req = InjuryPredictionRequest(sleepMinutes=420, steps=5000)
        q = calculate_data_quality_score(req)
        assert q["has_hard_blocker"] is True
        assert "userId" in q["hard_missing"]
        assert "date" in q["hard_missing"]

    def test_recovery_via_survey_without_sleep(self):
        req = InjuryPredictionRequest(
            userId="u1",
            date="2026-04-30",
            steps=8000,
            stressLevel=40,
            muscleSoreness=3,
        )
        q = calculate_data_quality_score(req)
        assert "recovery_signal" not in q["hard_missing"]

    def test_sensitive_missing_reduces_score(self):
        req = InjuryPredictionRequest(
            userId="u1",
            date="2026-04-30",
            sleepMinutes=420,
            steps=8000,
        )
        q = calculate_data_quality_score(req)
        assert len(q["sensitive_missing"]) >= 3
        assert float(q["score"]) < 1.0


class TestValidateFeatureVector:
    def test_passes_with_valid_defaults(self, model_feature_row):
        aligned = validate_feature_vector_for_model(
            model_feature_row,
            {"feature_columns": MODEL_FEATURE_COLUMNS, "estimator": None},
        )
        assert list(aligned.columns) == MODEL_FEATURE_COLUMNS
        assert aligned.dtypes.apply(lambda t: pd.api.types.is_float_dtype(t)).all()

    def test_raises_on_nan(self, model_feature_row):
        bad = model_feature_row.copy()
        bad.at[bad.index[0], "age"] = float("nan")
        with pytest.raises(ValidationError, match="NaN"):
            validate_feature_vector_for_model(
                bad, {"feature_columns": MODEL_FEATURE_COLUMNS, "estimator": None}
            )

    @pytest.mark.parametrize(
        ("column", "value", "pattern"),
        [
            ("stress_level", 0.5, "stress_level"),
            ("muscle_soreness", 11.0, "muscle_soreness"),
            ("age", 5.0, "age"),
            ("acwr_ratio", 3.5, "acwr_ratio"),
            ("injured_yesterday", 2.0, "injured_yesterday"),
        ],
    )
    def test_raises_on_out_of_range_values(self, model_feature_row, column, value, pattern):
        bad = model_feature_row.copy()
        bad.at[bad.index[0], column] = value
        with pytest.raises(ValidationError, match=pattern):
            validate_feature_vector_for_model(
                bad, {"feature_columns": MODEL_FEATURE_COLUMNS, "estimator": None}
            )


class TestInjuryRequestToDataframe:
    def test_distance_from_meters_over_steps(self):
        req = InjuryPredictionRequest(
            sleepMinutes=420,
            steps=1000,
            distanceMeters=10000,
        )
        df = injury_request_to_model_dataframe(req)
        assert df["daily_distance_km"].iloc[0] == pytest.approx(10.0)

    def test_steps_proxy_when_no_distance(self):
        req = InjuryPredictionRequest(sleepMinutes=420, steps=10000)
        df = injury_request_to_model_dataframe(req)
        assert df["daily_distance_km"].iloc[0] == pytest.approx(8.0)

    def test_all_values_finite(self, sample_prediction_request):
        df = injury_request_to_model_dataframe(sample_prediction_request)
        values = df.iloc[0].tolist()
        assert all(math.isfinite(v) for v in values)
