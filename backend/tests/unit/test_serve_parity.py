"""Unit tests for ML train-serve parity augmentation."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ML_ROOT = Path(__file__).resolve().parents[3] / "ML_model"
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

from training.pipeline import add_sequential_features  # noqa: E402
from training.serve_parity import (  # noqa: E402
    HISTORY_ROLLING_FEATURES,
    apply_low_confidence_defaults,
    apply_nutrition_population_defaults,
    apply_train_serve_parity_augmentation,
    build_cold_start_mask,
    compute_serve_derived_features,
    load_contract_defaults,
    nutrition_defaults_from_contract,
)

pytestmark = pytest.mark.unit


def _sample_row() -> pd.Series:
    defaults = load_contract_defaults()
    row = pd.Series(defaults)
    row["athlete_id"] = 1
    row["date"] = pd.Timestamp("2025-01-15")
    row["injury_today"] = 0
    row["acute_load_7d"] = 8.5
    row["acwr_ratio"] = 1.9
    row["acwr_ratio_ma7"] = 1.7
    row["sleep_hours_ma7"] = 6.2
    row["sleep_debt_3d"] = 4.5
    row["hrv_drop"] = 6.0
    row["load_recovery_imbalance"] = 8.55
    row["nutrition_intake_calories"] = 1800.0
    row["daily_calories"] = 1750.0
    row["total_calories_burned"] = 2100.0
    row["calorie_balance"] = -350.0
    return row


class TestServeDerivedFeatures:
    def test_compute_serve_derived_features_matches_backend_formula(self):
        row = {
            "daily_distance_km": 5.0,
            "active_calories_burned": 360.0,
            "sleep_hours": 6.0,
            "hrv_score": 58.0,
            "resting_hr": 56.0,
            "total_calories_burned": 0.0,
            "bmr_calories": 1600.0,
        }
        derived = compute_serve_derived_features(row)
        assert derived["acute_load_7d"] == pytest.approx(5.55)
        assert 0.35 <= derived["acwr_ratio"] <= 2.8
        assert derived["sleep_debt_3d"] == pytest.approx(2.5)  # (8 - 6) * 1.25
        assert derived["total_calories_burned"] == 1960.0


class TestLowConfidenceDefaults:
    def test_apply_low_confidence_defaults_replaces_rolling_features(self):
        defaults = load_contract_defaults()
        row = _sample_row()
        out = apply_low_confidence_defaults(row, defaults)

        for column in HISTORY_ROLLING_FEATURES:
            assert out[column] == defaults[column]

        expected_imbalance = defaults["acwr_ratio"] * defaults["sleep_debt_3d"]
        assert out["load_recovery_imbalance"] == pytest.approx(expected_imbalance)


class TestNutritionDefaults:
    def test_apply_nutrition_population_defaults(self):
        defaults = load_contract_defaults()
        nutrition = nutrition_defaults_from_contract(defaults)
        row = _sample_row()
        out = apply_nutrition_population_defaults(row, nutrition)

        assert out["nutrition_intake_calories"] == 2600.0
        assert out["daily_calories"] == 2600.0
        assert out["calorie_balance"] == pytest.approx(2600.0 - 2100.0)


class TestColdStartMask:
    def test_first_days_always_masked(self):
        rows = []
        for day in range(1, 11):
            rows.append({"athlete_id": 1, "date": f"2025-01-{day:02d}"})
        df = pd.DataFrame(rows)
        mask = build_cold_start_mask(df, first_n_days=7, target_fraction=0.25, seed=42)
        assert mask.iloc[:7].all()
        assert mask.sum() >= 7


class TestAugmentationIntegration:
    def test_augmentation_targets_fraction_on_demo_fixture(self):
        fixture = ML_ROOT / "fixtures" / "athlete_injury_demo.csv"
        df = add_sequential_features(pd.read_csv(fixture, parse_dates=["date"]))
        augmented, stats = apply_train_serve_parity_augmentation(df, seed=42)

        assert stats["enabled"] is True
        assert stats["rows"] == len(df)
        assert 0.20 <= stats["cold_start_fraction_actual"] <= 0.30
        assert 0.20 <= stats["nutrition_mask_fraction_actual"] <= 0.30
        assert len(augmented) == len(df)

        mask = build_cold_start_mask(df, first_n_days=7, target_fraction=0.25, seed=42)
        cold_idx = df.index[mask][0]
        defaults = load_contract_defaults()
        for column in HISTORY_ROLLING_FEATURES:
            assert augmented.at[cold_idx, column] == defaults[column]
