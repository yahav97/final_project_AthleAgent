"""Post-simulation feature engineering and dataset validation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from feature_contract import (
    assert_finite_feature_columns,
    assert_whole_number_columns,
    normalize_whole_number_columns,
)
from policy_config import DEFAULT_SLEEP_TARGET_HOURS


def add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add rolling and interaction features after per-day simulation."""
    out = df.copy()

    # ACWR (Acute:Chronic Workload Ratio) — acute load: 7-day rolling average
    out["acute_load_7d"] = out.groupby("athlete_id")["daily_distance_km"].transform(
        lambda x: x.rolling(7, min_periods=1).mean()
    )

    def _acwr_ratio_from_distances(distances: pd.Series) -> pd.Series:
        acute = distances.rolling(7, min_periods=1).mean()
        weekly_std = distances.rolling(7, min_periods=1).std().fillna(0.0)
        acute_vals = np.asarray(acute, dtype=float)
        weekly_std_vals = np.asarray(weekly_std, dtype=float)
        baseline_raw = pd.Series(
            acute_vals * 0.85 + weekly_std_vals * 0.35 + 0.5,
            index=distances.index,
        )
        baseline = baseline_raw.where(baseline_raw >= 0.55, 0.55)
        ratio = pd.Series(acute_vals, index=distances.index) / baseline.replace(0, np.nan)
        return ratio.fillna(1.0).clip(0.35, 2.8)

    out["acwr_ratio"] = out.groupby("athlete_id")["daily_distance_km"].transform(
        _acwr_ratio_from_distances
    )

    out["calorie_balance"] = out["daily_calories"] - out["total_calories_burned"]

    sleep_target = DEFAULT_SLEEP_TARGET_HOURS
    out["sleep_debt_3d"] = out.groupby("athlete_id")["sleep_hours"].transform(
        lambda x: (sleep_target - x).clip(lower=0).rolling(3, min_periods=1).sum()
    )

    out["hrv_rolling_7d"] = out.groupby("athlete_id")["hrv_score"].transform(
        lambda x: x.rolling(7, min_periods=1).mean()
    )
    out["hrv_drop"] = (out["hrv_score"] - out["hrv_rolling_7d"]).clip(-15.0, 15.0)

    out["load_recovery_imbalance"] = out["acwr_ratio"] * out["sleep_debt_3d"]
    out["speed_intensity_ratio"] = (out["max_speed"] / (out["avg_speed"] + 0.1)).clip(0.0, 5.0)

    return out


def finalize_dataset(
    df: pd.DataFrame,
    *,
    num_athletes: int,
    days_per_athlete: int,
) -> pd.DataFrame:
    """Apply derived features, cleanup, and row-count validation."""
    enriched = add_derived_features(df)
    final_df = enriched.dropna().drop(
        ["hrv_rolling_7d"],  # intermediate — hrv_drop is retained
        axis=1,
    )
    final_df = final_df.sort_values(["athlete_id", "date"]).reset_index(drop=True)
    final_df = normalize_whole_number_columns(final_df)
    assert_whole_number_columns(final_df)
    model_feature_cols = [
        column
        for column in final_df.columns
        if column not in {"athlete_id", "date", "injury_today"}
    ]
    assert_finite_feature_columns(final_df, model_feature_cols)

    expected_rows = num_athletes * days_per_athlete
    actual_rows = len(final_df)
    if actual_rows != expected_rows:
        raise ValueError(
            f"Expected {expected_rows:,} rows "
            f"({num_athletes} athletes × {days_per_athlete} days) but got {actual_rows:,}. "
            "Check rolling-window min_periods and dropna logic."
        )
    return final_df
