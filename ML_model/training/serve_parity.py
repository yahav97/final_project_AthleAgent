"""Train-serve parity augmentation — mirror backend cold-start and nutrition defaults.

Production path (thin history / missing meals):
- ``prediction/confidence.py`` replaces rolling features with contract defaults.
- ``nutrition_defaults.py`` fills weak nutrition with population averages.

During training, synthetic rows always have full athlete history. This module
randomly masks a fraction of days so the model sees serve-time feature values.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from policy_config import (
    DEFAULT_COLD_START_AUGMENT_FRACTION,
    DEFAULT_COLD_START_FIRST_N_DAYS,
    DEFAULT_NUTRITION_MASK_FRACTION,
    DEFAULT_SLEEP_DEBT_SINGLE_DAY_PROXY_SCALE,
    DEFAULT_SLEEP_TARGET_HOURS,
)

# Matches backend/services/prediction/confidence.py HISTORY_ROLLING_FEATURES.
HISTORY_ROLLING_FEATURES: tuple[str, ...] = (
    "acute_load_7d",
    "acwr_ratio",
    "acwr_ratio_ma7",
    "sleep_hours_ma7",
    "sleep_debt_3d",
    "hrv_drop",
)

NUTRITION_FEATURE_COLUMNS: tuple[str, ...] = (
    "nutrition_intake_calories",
    "daily_calories",
)

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "backend" / "data" / "model_feature_contract.json"


def load_contract_defaults() -> dict[str, float]:
    """Population defaults from backend/data/model_feature_contract.json."""
    with CONTRACT_PATH.open(encoding="utf-8") as handle:
        data = json.load(handle)
    defaults = data["default_values"]
    if not isinstance(defaults, dict):
        raise ValueError("model_feature_contract.json: default_values must be an object")
    return {str(key): float(value) for key, value in defaults.items()}


def nutrition_defaults_from_contract(contract_defaults: dict[str, float]) -> dict[str, float]:
    """Nutrition imputation values aligned with backend NUTRITION_DEFAULT_CALORIES (2600)."""
    calories = float(contract_defaults["nutrition_intake_calories"])
    return {
        "nutrition_intake_calories": calories,
        "daily_calories": float(contract_defaults["daily_calories"]),
        "calorie_balance": float(contract_defaults["calorie_balance"]),
    }


def acwr_baseline_from_acute_proxy(acute_load_7d: float) -> float:
    """Mirror backend/services/feature_engineering.acwr_baseline_from_acute_proxy."""
    return float(max(0.55, acute_load_7d * 0.78 + 1.35))


def acwr_ratio_bounded(acute_load_7d: float, baseline: float) -> float:
    """Mirror backend/services/feature_engineering.acwr_ratio_bounded."""
    if baseline <= 0:
        return 1.0
    return float(min(2.8, max(0.35, acute_load_7d / baseline)))


def compute_serve_derived_features(row: Mapping[str, Any]) -> dict[str, float]:
    """Mirror backend/services/feature_engineering.compute_derived_features."""
    daily_distance_km = float(row.get("daily_distance_km") or 0.0)
    active_calories = float(row.get("active_calories_burned") or 0.0)
    sleep_hours = float(row.get("sleep_hours") or 7.0)
    hrv_score = float(row.get("hrv_score") or 62.0)
    resting_hr = float(row.get("resting_hr") or 54.0)
    bmr_calories = float(row.get("bmr_calories") or 0.0)

    acute_load_7d = max(0.05, daily_distance_km * 0.95 + active_calories / 450.0)
    baseline = acwr_baseline_from_acute_proxy(acute_load_7d)
    acwr_ratio = acwr_ratio_bounded(acute_load_7d, baseline)

    sleep_target = float(DEFAULT_SLEEP_TARGET_HOURS)
    sleep_debt_scale = float(DEFAULT_SLEEP_DEBT_SINGLE_DAY_PROXY_SCALE)
    sleep_debt_3d = float(max(0.0, (sleep_target - sleep_hours) * sleep_debt_scale))

    baseline_hrv = 62.0
    hrv_drop = float(
        max(-15.0, min(15.0, baseline_hrv - hrv_score + (resting_hr - 54.0) * 0.15))
    )

    total_calories_burned = float(row.get("total_calories_burned") or 0.0)
    if total_calories_burned <= 0 and (active_calories > 0 or bmr_calories > 0):
        total_calories_burned = active_calories + bmr_calories

    return {
        "acute_load_7d": acute_load_7d,
        "acwr_ratio": acwr_ratio,
        "sleep_debt_3d": sleep_debt_3d,
        "hrv_drop": hrv_drop,
        "total_calories_burned": total_calories_burned,
    }


def apply_low_confidence_defaults(row: pd.Series, defaults: dict[str, float]) -> pd.Series:
    """Simulate backend LOW history confidence — all rolling features → population defaults."""
    out = row.copy()
    for column in HISTORY_ROLLING_FEATURES:
        if column in out.index:
            out[column] = defaults[column]
    acwr = float(out["acwr_ratio"])
    sleep_debt = float(out["sleep_debt_3d"])
    out["load_recovery_imbalance"] = acwr * sleep_debt
    return out


def apply_nutrition_population_defaults(
    row: pd.Series,
    nutrition_defaults: dict[str, float],
) -> pd.Series:
    """Simulate backend nutrition_defaults.apply_nutrition_population_defaults."""
    out = row.copy()
    for column in NUTRITION_FEATURE_COLUMNS:
        if column in out.index:
            out[column] = nutrition_defaults[column]
    total_burned = float(out.get("total_calories_burned") or 0.0)
    out["calorie_balance"] = float(out["daily_calories"]) - total_burned
    return out


def build_cold_start_mask(
    df: pd.DataFrame,
    *,
    first_n_days: int,
    target_fraction: float,
    seed: int,
) -> pd.Series:
    """
    Mark rows that simulate cold-start / thin-history serving.

    Always includes the first ``first_n_days`` per athlete, then randomly samples
  additional days until ~``target_fraction`` of each athlete's rows are covered.
    """
    cold_start = pd.Series(False, index=df.index)
    rng = np.random.default_rng(seed)

    for _, group in df.groupby("athlete_id", sort=False):
        ordered = group.sort_values("date")
        indices = ordered.index
        n = len(indices)
        if n == 0:
            continue

        target_count = max(1, int(round(n * target_fraction)))
        target_count = min(n, target_count)

        first_count = min(first_n_days, n)
        cold_start.loc[indices[:first_count]] = True

        already = int(cold_start.loc[indices].sum())
        extra_needed = max(0, target_count - already)
        if extra_needed <= 0:
            continue

        remaining = indices[first_count:]
        if len(remaining) == 0:
            continue

        pick_n = min(extra_needed, len(remaining))
        chosen = rng.choice(remaining.to_numpy(), size=pick_n, replace=False)
        cold_start.loc[chosen] = True

    return cold_start


def apply_train_serve_parity_augmentation(
    df: pd.DataFrame,
    *,
    cold_start_fraction: float = DEFAULT_COLD_START_AUGMENT_FRACTION,
    cold_start_first_n_days: int = DEFAULT_COLD_START_FIRST_N_DAYS,
    nutrition_mask_fraction: float = DEFAULT_NUTRITION_MASK_FRACTION,
    seed: int = 42,
    enabled: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Apply serve-time feature masking on a post-``add_sequential_features`` frame.

    Returns ``(augmented_df, stats)`` for manifest logging.
    """
    if not enabled or df.empty:
        return df, {"enabled": False, "rows": len(df)}

    contract_defaults = load_contract_defaults()
    nutrition_defaults = nutrition_defaults_from_contract(contract_defaults)
    rng = np.random.default_rng(seed + 1)

    out = df.copy()
    cold_start_mask = build_cold_start_mask(
        out,
        first_n_days=cold_start_first_n_days,
        target_fraction=cold_start_fraction,
        seed=seed,
    )
    nutrition_mask = pd.Series(rng.random(len(out)) < nutrition_mask_fraction, index=out.index)

    for column in HISTORY_ROLLING_FEATURES:
        if column in out.columns:
            out.loc[cold_start_mask, column] = contract_defaults[column]
    out.loc[cold_start_mask, "load_recovery_imbalance"] = (
        contract_defaults["acwr_ratio"] * contract_defaults["sleep_debt_3d"]
    )

    for column in NUTRITION_FEATURE_COLUMNS:
        if column in out.columns:
            out.loc[nutrition_mask, column] = nutrition_defaults[column]
    out.loc[nutrition_mask, "calorie_balance"] = (
        out.loc[nutrition_mask, "daily_calories"] - out.loc[nutrition_mask, "total_calories_burned"]
    )

    stats: dict[str, Any] = {
        "enabled": True,
        "rows": int(len(out)),
        "cold_start_fraction_target": float(cold_start_fraction),
        "cold_start_first_n_days": int(cold_start_first_n_days),
        "cold_start_rows": int(cold_start_mask.sum()),
        "cold_start_fraction_actual": float(cold_start_mask.mean()),
        "nutrition_mask_fraction_target": float(nutrition_mask_fraction),
        "nutrition_mask_rows": int(nutrition_mask.sum()),
        "nutrition_mask_fraction_actual": float(nutrition_mask.mean()),
        "overlap_rows": int((cold_start_mask & nutrition_mask).sum()),
        "contract_path": str(CONTRACT_PATH.relative_to(CONTRACT_PATH.parents[2])).replace("\\", "/"),
        "nutrition_defaults": nutrition_defaults,
    }
    return out, stats
