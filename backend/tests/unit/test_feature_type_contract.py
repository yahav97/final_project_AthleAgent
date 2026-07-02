"""Train/serve feature type contract: whole numbers and safe derived ratios."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from schemas.inference import InjuryPredictionRequest
from services.model_features import (
    DEFAULT_FEATURE_VALUES,
    INTEGER_FEATURE_COLUMNS,
    MODEL_FEATURE_COLUMNS,
    coerce_whole_number_features,
)
from services.preprocessing import injury_request_to_model_dataframe

pytestmark = pytest.mark.unit

_FIXTURE_CSV = (
    Path(__file__).resolve().parents[3] / "ML_model" / "fixtures" / "athlete_injury_demo.csv"
)


class TestIntegerFeatureContract:
    def test_defaults_are_whole_numbers(self):
        for column in INTEGER_FEATURE_COLUMNS:
            value = DEFAULT_FEATURE_VALUES[column]
            assert value == pytest.approx(round(value)), f"{column} default is not whole: {value}"

    def test_coerce_whole_number_features_rounds_fractions(self):
        features = {"stress_level": 4.6, "muscle_soreness": 5.5, "daily_distance_km": 3.14}
        coerced = coerce_whole_number_features(features)
        assert coerced["stress_level"] == pytest.approx(5.0)
        assert coerced["muscle_soreness"] == pytest.approx(6.0)
        assert coerced["daily_distance_km"] == pytest.approx(3.14)

    def test_request_dataframe_integer_columns_are_whole(self, sample_prediction_request):
        frame = injury_request_to_model_dataframe(sample_prediction_request)
        for column in INTEGER_FEATURE_COLUMNS:
            value = float(frame[column].iloc[0])
            assert value == pytest.approx(round(value)), f"{column}={value} is not whole"

    def test_survey_fields_map_to_whole_numbers(self):
        req = InjuryPredictionRequest(
            age=28,
            sleepMinutes=420,
            steps=8000,
            stressLevel=35,
            muscleSoreness=3,
            energyLevel=65,
        )
        frame = injury_request_to_model_dataframe(req)
        for column in ("stress_level", "muscle_soreness", "energy_level"):
            value = float(frame[column].iloc[0])
            assert value == pytest.approx(round(value))

    def test_speed_intensity_ratio_safe_when_avg_speed_zero(self):
        req = InjuryPredictionRequest(age=28, sleepMinutes=0, steps=0, distanceMeters=0)
        frame = injury_request_to_model_dataframe(req)
        ratio = float(frame["speed_intensity_ratio"].iloc[0])
        assert math.isfinite(ratio)
        assert ratio == pytest.approx(0.0)

    def test_all_model_columns_finite(self, sample_prediction_request):
        frame = injury_request_to_model_dataframe(sample_prediction_request)
        for column in MODEL_FEATURE_COLUMNS:
            value = float(frame[column].iloc[0])
            assert math.isfinite(value), column


@pytest.mark.skipif(not _FIXTURE_CSV.is_file(), reason="fixture CSV not present")
class TestSyntheticFixtureTypes:
    def test_integer_columns_in_fixture_are_whole(self):
        df = pd.read_csv(_FIXTURE_CSV)
        for column in INTEGER_FEATURE_COLUMNS:
            if column not in df.columns:
                continue
            series = pd.to_numeric(df[column], errors="coerce").dropna()
            remainder = np.abs(series % 1.0)
            assert (remainder <= 1e-9).all(), f"{column} has fractional values in fixture"

    def test_derived_ratios_finite_in_fixture(self):
        df = pd.read_csv(_FIXTURE_CSV)
        for column in ("acwr_ratio", "speed_intensity_ratio", "load_recovery_imbalance"):
            series = pd.to_numeric(df[column], errors="coerce")
            assert np.isfinite(series.to_numpy(dtype=float)).all(), column
