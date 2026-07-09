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
    apply_train_serve_parity_augmentation,
    build_cold_start_mask,
    load_contract_defaults,
)

pytestmark = pytest.mark.unit


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
