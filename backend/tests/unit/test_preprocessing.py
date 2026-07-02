"""Unit tests for preprocessing scale mapping and feature validation."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from schemas.inference import InjuryPredictionRequest
from services.model_features import MODEL_FEATURE_COLUMNS
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
        [(80, 8.0), (5, 5.0), (150, 10.0)],
    )
    def test_stress_to_model_scale(self, raw, expected):
        assert _stress_to_model_scale(raw) == pytest.approx(expected)

    @pytest.mark.parametrize(
        ("raw", "expected_approx"),
        [(3, 5.5), (5, 9.5)],
    )
    def test_soreness_to_model_scale(self, raw, expected_approx):
        assert _soreness_to_model_scale(raw) == pytest.approx(expected_approx)

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [(70, 7.0), (100, 10.0)],
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

    def test_missing_user_and_date_does_not_hard_block(self):
        req = InjuryPredictionRequest(sleepMinutes=420, steps=5000)
        q = calculate_data_quality_score(req)
        assert q["has_hard_blocker"] is False

    def test_zero_steps_reduces_confidence_not_blocks(self):
        req = InjuryPredictionRequest(
            userId="u1",
            date="2026-04-30",
            sleepMinutes=420,
            steps=0,
            stressLevel=40,
            muscleSoreness=3,
            energyLevel=70,
        )
        q = calculate_data_quality_score(req)
        assert q["has_hard_blocker"] is False
        assert "steps" in q["weak_fields"]
        assert float(q["score"]) < 1.0

    def test_missing_optional_fields_not_penalized(self):
        req = InjuryPredictionRequest(
            userId="u1",
            date="2026-04-30",
            sleepMinutes=420,
            steps=8000,
            stressLevel=40,
            muscleSoreness=3,
            energyLevel=70,
        )
        q = calculate_data_quality_score(req)
        assert q["score"] == pytest.approx(1.0)
        assert q["weak_fields"] == []

    def test_active_calories_without_steps_still_scores(self):
        req = InjuryPredictionRequest(
            userId="u1",
            date="2026-04-30",
            sleepMinutes=420,
            steps=0,
            activeCalories=350,
            stressLevel=40,
            muscleSoreness=3,
            energyLevel=70,
        )
        q = calculate_data_quality_score(req)
        assert q["has_hard_blocker"] is False
        assert "steps" in q["weak_fields"]
        assert "activeCalories" not in q["weak_fields"]

    def test_nutrition_imputed_reduces_quality_score(self):
        base = InjuryPredictionRequest(
            userId="u1",
            date="2026-04-30",
            sleepMinutes=420,
            steps=8000,
            distanceMeters=6000,
            heartRateAvg=58,
            stressLevel=30,
            muscleSoreness=3,
            energyLevel=70,
            hrvRmssd=65.0,
            restingHeartRate=52,
        )
        without = calculate_data_quality_score(base)
        with_imputed = calculate_data_quality_score(
            base.model_copy(update={"nutritionImputed": True})
        )
        assert without["score"] == pytest.approx(1.0)
        assert with_imputed["score"] < without["score"]
        assert "nutrition_imputed" in with_imputed["weak_fields"]

    def test_weak_fields_reduce_score(self):
        req = InjuryPredictionRequest(
            userId="u1",
            date="2026-04-30",
            sleepMinutes=0,
            steps=0,
            distanceMeters=0,
        )
        q = calculate_data_quality_score(req)
        assert len(q["weak_fields"]) >= 3
        assert float(q["score"]) < 1.0


class TestValidateFeatureVector:
    def test_passes_with_valid_defaults(self, model_feature_row):
        aligned = validate_feature_vector_for_model(
            model_feature_row,
            {"feature_columns": MODEL_FEATURE_COLUMNS, "estimator": None},
        )
        assert list(aligned.columns) == MODEL_FEATURE_COLUMNS
        assert aligned.dtypes.apply(lambda t: pd.api.types.is_float_dtype(t)).all()

    def test_coerces_nan_to_zero(self, model_feature_row):
        bad = model_feature_row.copy()
        bad.at[bad.index[0], "age"] = float("nan")
        aligned = validate_feature_vector_for_model(
            bad, {"feature_columns": MODEL_FEATURE_COLUMNS, "estimator": None}
        )
        assert aligned["age"].iloc[0] == pytest.approx(0.0)

    @pytest.mark.parametrize(
        ("column", "value"),
        [
            ("stress_level", 0.5),
            ("muscle_soreness", 11.0),
            ("acwr_ratio", 3.5),
            ("injured_yesterday", 2.0),
            ("nutrition_intake_calories", 12000.0),
        ],
    )
    def test_accepts_out_of_range_values(self, model_feature_row, column, value):
        row = model_feature_row.copy()
        row.at[row.index[0], column] = value
        aligned = validate_feature_vector_for_model(
            row, {"feature_columns": MODEL_FEATURE_COLUMNS, "estimator": None}
        )
        assert aligned[column].iloc[0] == pytest.approx(float(value))


class TestInjuryRequestToDataframe:
    def test_missing_age_raises(self):
        req = InjuryPredictionRequest(sleepMinutes=420, steps=10000)
        with pytest.raises(ValidationError) as exc_info:
            injury_request_to_model_dataframe(req)
        assert exc_info.value.code == "missing_age"

    def test_distance_from_meters_over_steps(self):
        req = InjuryPredictionRequest(
            age=28,
            sleepMinutes=420,
            steps=1000,
            distanceMeters=10000,
            stressLevel=40,
            muscleSoreness=3,
            energyLevel=70,
        )
        df = injury_request_to_model_dataframe(req)
        assert df["daily_distance_km"].iloc[0] == pytest.approx(10.0)

    def test_steps_proxy_when_no_distance(self):
        req = InjuryPredictionRequest(
            age=28,
            sleepMinutes=420,
            steps=10000,
            stressLevel=40,
            muscleSoreness=3,
            energyLevel=70,
        )
        df = injury_request_to_model_dataframe(req)
        assert df["daily_distance_km"].iloc[0] == pytest.approx(8.0)

    def test_extreme_distance_not_clamped(self):
        req = InjuryPredictionRequest(
            age=28,
            sleepMinutes=420,
            steps=80000,
            distanceMeters=50000,
            stressLevel=40,
            muscleSoreness=3,
            energyLevel=70,
        )
        df = injury_request_to_model_dataframe(req)
        assert df["daily_distance_km"].iloc[0] == pytest.approx(50.0)

    def test_zero_sleep_passes_through(self):
        req = InjuryPredictionRequest(
            age=28,
            sleepMinutes=0,
            steps=5000,
            stressLevel=40,
            muscleSoreness=3,
            energyLevel=70,
        )
        df = injury_request_to_model_dataframe(req)
        assert df["sleep_hours"].iloc[0] == pytest.approx(0.0)

    def test_all_values_finite(self, sample_prediction_request):
        df = injury_request_to_model_dataframe(sample_prediction_request)
        values = df.iloc[0].tolist()
        assert all(math.isfinite(v) for v in values)
