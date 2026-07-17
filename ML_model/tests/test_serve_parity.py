"""Minimal tests for train-serve parity augmentation."""

from __future__ import annotations

import pandas as pd

from training.serve_parity import (
    HISTORY_ROLLING_FEATURES,
    apply_train_serve_parity_augmentation,
    load_contract_defaults,
)


def test_cold_start_rows_use_contract_rolling_defaults():
    defaults = load_contract_defaults()
    df = pd.DataFrame(
        {
            "athlete_id": [1, 1, 1, 1],
            "date": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
            "acwr_ratio": [1.5, 1.6, 1.7, 1.8],
            "sleep_debt_3d": [2.0, 2.1, 2.2, 2.3],
            "acwr_ratio_ma7": [1.4, 1.5, 1.6, 1.7],
            "sleep_hours_ma7": [6.5, 6.6, 6.7, 6.8],
            "acute_load_7d": [5.0, 5.1, 5.2, 5.3],
            "hrv_drop": [-1.0, -1.1, -1.2, -1.3],
            "daily_calories": [2600.0] * 4,
            "total_calories_burned": [1990.0] * 4,
        }
    )
    out, stats = apply_train_serve_parity_augmentation(
        df,
        cold_start_fraction=1.0,
        cold_start_first_n_days=4,
        nutrition_mask_fraction=0.0,
        seed=42,
    )
    assert stats["cold_start_rows"] == 4
    for column in HISTORY_ROLLING_FEATURES:
        assert (out[column] == defaults[column]).all()
