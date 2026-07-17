"""
Derived workload and recovery metrics (ACWR-style) from sparse mobile payloads.

Training reference: ``ML_model/generation/postprocess.py`` — 7-day rolling mean of
``daily_distance_km`` only (no active-calorie term in ACWR).
"""

from __future__ import annotations

from typing import Any, Mapping

from config import settings

DerivedFeatures = dict[str, float]

ACUTE_LOAD_FLOOR = 0.05


def acwr_baseline_from_weekly_stats(weekly_mean: float, weekly_std: float = 0.0) -> float:
    """Internal ACWR denominator from 7-day distance mean/std (not a model feature)."""
    return float(max(0.55, weekly_mean * 0.85 + weekly_std * 0.35 + 0.5))


def acwr_ratio_bounded(acute_load_7d: float, baseline: float) -> float:
    """Clamp ACWR to [0.35, 2.8] — same range as training ``postprocess`` / simulator."""
    if baseline <= 0:
        return 1.0
    return float(min(2.8, max(0.35, acute_load_7d / baseline)))


def _rolling_std_ddof1(values: list[float]) -> float:
    """Match ``pandas.Series.rolling(...).std()`` default (sample std, ddof=1)."""
    n = len(values)
    if n <= 1:
        return 0.0
    mean = sum(values) / n
    variance = sum((value - mean) ** 2 for value in values) / (n - 1)
    return float(variance**0.5)


def acwr_features_from_distance_history(
    daily_distance_km: list[float] | tuple[float, ...],
) -> tuple[float, float]:
    """
    Acute load + ACWR from a distance series — matches training ``postprocess.py``.

    Uses the last up-to-7 days with ``min_periods=1`` (single-day cold-start included).
    """
    tail = [float(distance) for distance in daily_distance_km[-7:]]
    if not tail:
        return ACUTE_LOAD_FLOOR, 1.0

    acute_load_7d = float(max(ACUTE_LOAD_FLOOR, sum(tail) / len(tail)))
    weekly_std = _rolling_std_ddof1(tail)
    baseline = acwr_baseline_from_weekly_stats(acute_load_7d, weekly_std)
    acwr_ratio = acwr_ratio_bounded(acute_load_7d, baseline)
    return acute_load_7d, acwr_ratio


def _active_calories_from_row(row: Mapping[str, Any]) -> float:
    return float(row.get("active_calories_burned") or 0.0)


def _bmr_calories_from_row(row: Mapping[str, Any]) -> float:
    return float(row.get("bmr_calories") or 0.0)


def daily_sleep_deficit_hours(
    sleep_hours: float,
    *,
    sleep_target: float | None = None,
) -> float:
    """Per-day deficit vs target; surplus sleep (oversleep) counts as zero debt."""
    target = float(settings.SLEEP_TARGET_HOURS if sleep_target is None else sleep_target)
    return float(max(0.0, target - float(sleep_hours)))


def sleep_debt_3d_from_sleep_hours(
    sleep_hours: list[float] | tuple[float, ...],
    *,
    sleep_target: float | None = None,
) -> float:
    """
    Rolling 3-day sleep debt — matches ``ML_model/generation/postprocess.py``:

    sum of ``max(0, target - sleep_hours)`` over the last up-to-3 days.
    """
    target = float(settings.SLEEP_TARGET_HOURS if sleep_target is None else sleep_target)
    tail = list(sleep_hours)[-3:]
    return float(sum(max(0.0, target - hours) for hours in tail))


def compute_derived_features(row: Mapping[str, Any]) -> DerivedFeatures:
    """
    Compute acute/chronic load, ACWR, sleep debt, HRV drop proxy,
    and total_calories_burned from active + BMR.

    ``row`` uses model-side names from ``base_model_features_from_request``
    (e.g. daily_distance_km, sleep_hours, active_calories_burned, bmr_calories).

    ACWR (distance-only, same as training):
        - acute_load_7d: mean ``daily_distance_km`` over up-to-7 days (1 day at cold-start).
        - acwr_ratio: acute / weekly baseline from distance mean + std (capped 0.35–2.8).

    ``sleep_debt_3d`` with one day uses the same formula as training with
    ``rolling(3, min_periods=1)`` — not a separate scaled proxy.
    """
    daily_distance_km = float(row.get("daily_distance_km") or 0.0)
    active_calories = _active_calories_from_row(row)
    sleep_hours = float(row.get("sleep_hours") or 7.0)
    hrv_score = float(row.get("hrv_score") or 62.0)
    resting_hr = float(row.get("resting_hr") or 54.0)
    bmr_calories = _bmr_calories_from_row(row)

    acute_load_7d, acwr_ratio = acwr_features_from_distance_history([daily_distance_km])

    sleep_target = float(settings.SLEEP_TARGET_HOURS)
    resolved_sleep_hours = float(row.get("sleep_hours") or 7.0)
    sleep_debt_3d = sleep_debt_3d_from_sleep_hours([resolved_sleep_hours], sleep_target=sleep_target)

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
