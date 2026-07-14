"""
Derived workload and recovery metrics (ACWR-style) from sparse mobile payloads.

Training reference: ML_model/data_generator.py (rolling 7d on full history).
Here we only have a single day snapshot, so we document transparent proxies.
"""

from __future__ import annotations

from typing import Any, Mapping

from config import settings

DerivedFeatures = dict[str, float]


def acwr_baseline_from_weekly_stats(weekly_mean: float, weekly_std: float = 0.0) -> float:
    """Internal ACWR denominator from 7-day distance mean/std (not a model feature)."""
    return float(max(0.55, weekly_mean * 0.85 + weekly_std * 0.35 + 0.5))


def acwr_baseline_from_acute_proxy(acute_load_7d: float) -> float:
    """Single-day fallback when Firestore history is unavailable."""
    return float(max(0.55, acute_load_7d * 0.78 + 1.35))


def acwr_ratio_bounded(acute_load_7d: float, baseline: float) -> float:
    """Clamp ACWR to [0.35, 2.8] — same range as training ``postprocess`` / simulator."""
    if baseline <= 0:
        return 1.0
    return float(min(2.8, max(0.35, acute_load_7d / baseline)))


def _active_calories_from_row(row: Mapping[str, Any]) -> float:
    return float(
        row.get("active_calories_burned")
        or row.get("_active_calories")  # legacy test key
        or 0.0
    )


def _bmr_calories_from_row(row: Mapping[str, Any]) -> float:
    return float(row.get("bmr_calories") or row.get("_bmr_calories") or 0.0)


def compute_derived_features(row: Mapping[str, Any]) -> DerivedFeatures:
    """
    Compute acute/chronic load, ACWR, sleep debt proxy, HRV drop proxy,
    and total_calories_burned from active + BMR.

    ``row`` uses model-side names from ``base_model_features_from_request``
    (e.g. daily_distance_km, sleep_hours, active_calories_burned, bmr_calories).

    ACWR proxy (single day, no athlete history):
        - acute_load_7d: combines distance and active calories as acute exposure.
        - acwr_ratio: acute / internal baseline (capped 0.35–2.8).
    """
    daily_distance_km = float(row.get("daily_distance_km") or 0.0)
    active_calories = _active_calories_from_row(row)
    sleep_hours = float(row.get("sleep_hours") or 7.0)
    hrv_score = float(row.get("hrv_score") or 62.0)
    resting_hr = float(row.get("resting_hr") or 54.0)
    bmr_calories = _bmr_calories_from_row(row)

    # Single-day acute load proxy: distance dominates; active calories dampened (~450 kcal ≈ 1 km).
    acute_load_7d = max(0.05, daily_distance_km * 0.95 + active_calories / 450.0)
    baseline = acwr_baseline_from_acute_proxy(acute_load_7d)
    acwr_ratio = acwr_ratio_bounded(acute_load_7d, baseline)

    sleep_target = float(settings.SLEEP_TARGET_HOURS)
    sleep_debt_scale = float(settings.SLEEP_DEBT_SINGLE_DAY_PROXY_SCALE)
    sleep_debt_3d = float(max(0.0, (sleep_target - sleep_hours) * sleep_debt_scale))

    # Population mid-range HRV/RHR anchors used only when no rolling athlete baseline exists.
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
        "total_calories_burned": float(total_calories_burned),
    }
