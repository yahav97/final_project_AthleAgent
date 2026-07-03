"""Post-simulation feature engineering, validation, and quality report."""

from __future__ import annotations

import json
import os

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


def write_quality_report(
    df: pd.DataFrame,
    output_dir: str,
    *,
    expected_rows: int | None = None,
) -> str:
    """Write dataset quality diagnostics JSON and return path."""
    class_counts = df["injury_today"].value_counts().to_dict()
    injury_rate = float(df["injury_today"].mean())
    corr_cols = ["daily_distance_km", "sleep_hours", "stress_level", "muscle_soreness", "acwr_ratio", "hrv_drop"]
    corr = df.loc[:, corr_cols].corr()
    report = {
        "rows": int(len(df)),
        "expected_rows": int(expected_rows if expected_rows is not None else len(df)),
        "columns": int(df.shape[1]),
        "injury_rate": injury_rate,
        "class_counts": {str(k): int(v) for k, v in class_counts.items()},
        "acwr_ratio_range": [float(df["acwr_ratio"].min()), float(df["acwr_ratio"].max())],
        "sleep_debt_3d_range": [float(df["sleep_debt_3d"].min()), float(df["sleep_debt_3d"].max())],
        "hrv_drop_range": [float(df["hrv_drop"].min()), float(df["hrv_drop"].max())],
        "spo2_range": [float(df["spo2"].min()), float(df["spo2"].max())],
        "respiratory_rate_range": [float(df["respiratory_rate"].min()), float(df["respiratory_rate"].max())],
        "vo2_max_range": [float(df["vo2_max"].min()), float(df["vo2_max"].max())],
        "elevation_gained_range": [float(df["elevation_gained_m"].min()), float(df["elevation_gained_m"].max())],
        "high_risk_condition_rates": {
            "acwr_gt_1_4": float((df["acwr_ratio"] > 1.4).mean()),
            "sleep_debt_gt_5": float((df["sleep_debt_3d"] > 5.0).mean()),
            "hrv_drop_lt_minus8": float((df["hrv_drop"] < -8.0).mean()),
            "stress_ge_8": float((df["stress_level"] >= 8).mean()),
            "spo2_lt_94": float((df["spo2"] < 94.0).mean()),
        },
        "feature_correlations": {
            "distance_sleep": float(corr.loc["daily_distance_km", "sleep_hours"]),
            "distance_soreness": float(corr.loc["daily_distance_km", "muscle_soreness"]),
            "stress_sleep": float(corr.loc["stress_level", "sleep_hours"]),
            "stress_hrvdrop": float(corr.loc["stress_level", "hrv_drop"]),
        },
    }
    output_path = os.path.join(output_dir, "dataset_quality_report.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return output_path
