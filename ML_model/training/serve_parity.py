"""Train-serve parity augmentation — mirror backend cold-start and nutrition defaults."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from feature_contract import CONTRACT_PATH, load_feature_contract
from policy_config import (
    DEFAULT_COLD_START_AUGMENT_FRACTION,
    DEFAULT_COLD_START_FIRST_N_DAYS,
    DEFAULT_NUTRITION_MASK_FRACTION,
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


def load_contract_defaults() -> dict[str, float]:
    """Population defaults from backend/data/model_feature_contract.json."""
    defaults = load_feature_contract().get("default_values")
    if not isinstance(defaults, dict):
        raise ValueError("model_feature_contract.json: default_values must be an object")
    return {str(key): float(value) for key, value in defaults.items()}


def nutrition_defaults_from_contract(contract_defaults: dict[str, float]) -> dict[str, float]:
    calories = float(contract_defaults["nutrition_intake_calories"])
    return {
        "nutrition_intake_calories": calories,
        "daily_calories": float(contract_defaults["daily_calories"]),
        "calorie_balance": float(contract_defaults["calorie_balance"]),
    }


def build_cold_start_mask(
    df: pd.DataFrame,
    *,
    first_n_days: int,
    target_fraction: float,
    seed: int,
) -> pd.Series:
    """
    Mark rows that mimic thin history at serve time.

    Always flags the first ``first_n_days`` per athlete, then samples more days
    until roughly ``target_fraction`` of rows (default 25%) are cold-start.
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
    Mirror backend defaults: replace rolling features on cold-start rows and
    occasionally impute nutrition columns (meals often missing in the app).
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
