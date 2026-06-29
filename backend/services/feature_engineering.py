"""
Derived workload and recovery metrics (ACWR-style) from sparse mobile payloads.

Training reference: ML_model/data_generator.py (rolling 7d on full history).
Here we only have a single day snapshot, so we document transparent proxies.
"""

from __future__ import annotations

from typing import Any, Mapping

from services.model_features import DEFAULT_FEATURE_VALUES


def acwr_baseline_from_weekly_stats(weekly_mean: float, weekly_std: float = 0.0) -> float:
    """Internal ACWR denominator from 7-day distance mean/std (not a model feature)."""
    return float(max(0.55, weekly_mean * 0.85 + weekly_std * 0.35 + 0.5))


def acwr_baseline_from_acute_proxy(acute_load_7d: float) -> float:
    """Single-day fallback when Firestore history is unavailable."""
    return float(max(0.55, acute_load_7d * 0.78 + 1.35))


def acwr_ratio_bounded(acute_load_7d: float, baseline: float) -> float:
    if baseline <= 0:
        return 1.0
    return float(min(2.8, max(0.35, acute_load_7d / baseline)))


def compute_derived_features(row: Mapping[str, Any]) -> dict[str, float]:
    """
    Compute acute/chronic load, ACWR, sleep debt proxy, HRV drop proxy,
    and total_calories_burned from active + BMR.

    ``row`` is a flat dict of *model-side* names already mapped from the request
    (e.g. daily_distance_km, sleep_hours, stress_level, …). Missing keys should be
    None or numeric; callers normalize before/after.

    ACWR proxy (single day, no athlete history):
        - acute_load_7d: combines distance and active calories as acute exposure.
        - acwr_ratio: acute / internal baseline (capped 0.35–2.8).
    """
    daily_distance_km = float(row.get("daily_distance_km") or 0.0)
    active_cal = float(row.get("active_calories_burned") or row.get("_active_calories") or 0.0)
    sleep_hours = float(row.get("sleep_hours") or 7.0)
    hrv_score = float(row.get("hrv_score") or 62.0)
    resting_hr = float(row.get("resting_hr") or 54.0)
    bmr_cal = float(row.get("_bmr_calories") or 0.0)

    acute_load_7d = max(0.05, daily_distance_km * 0.95 + active_cal / 450.0)
    baseline = acwr_baseline_from_acute_proxy(acute_load_7d)
    acwr_ratio = acwr_ratio_bounded(acute_load_7d, baseline)

    sleep_debt_3d = float(max(0.0, (8.0 - sleep_hours) * 1.25))

    baseline_hrv = 62.0
    hrv_drop = float(max(-15.0, min(15.0, baseline_hrv - hrv_score + (resting_hr - 54.0) * 0.15)))

    total_calories_burned = float(row.get("total_calories_burned") or 0.0)
    if total_calories_burned <= 0 and (active_cal > 0 or bmr_cal > 0):
        total_calories_burned = active_cal + bmr_cal
    if total_calories_burned <= 0:
        total_calories_burned = float(DEFAULT_FEATURE_VALUES["total_calories_burned"])

    return {
        "acute_load_7d": acute_load_7d,
        "acwr_ratio": acwr_ratio,
        "sleep_debt_3d": sleep_debt_3d,
        "hrv_drop": hrv_drop,
        "total_calories_burned": float(min(9000.0, total_calories_burned)),
    }
