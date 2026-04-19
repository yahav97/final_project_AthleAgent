"""
Derived workload and recovery metrics (ACWR-style) from sparse mobile payloads.

Training reference: ML_model/data_generator.py (rolling 7d / 21d on full history).
Here we only have a single day snapshot, so we document transparent proxies.
"""

from __future__ import annotations

from typing import Any, Mapping


def compute_derived_features(row: Mapping[str, Any]) -> dict[str, float]:
    """
    Compute acute/chronic load, ACWR, sleep debt proxy, and HRV drop proxy.

    ``row`` is a flat dict of *model-side* names already mapped from the request
    (e.g. daily_distance_km, sleep_hours, stress_level, …). Missing keys should be
    None or numeric; callers normalize before/after.

    ACWR proxy (single day, no athlete history):
        - acute_load_7d: combines distance and active calories as acute exposure.
        - chronic_load_21d: slow-varying baseline anchored below acute to avoid
          divide-by-zero and unrealistic spikes when distance is zero.
        - acwr_ratio: acute / chronic (capped at 2.8, ~injury-risk band in literature).
    """
    daily_distance_km = float(row.get("daily_distance_km") or 0.0)
    active_cal = float(row.get("_active_calories") or 0.0)
    sleep_hours = float(row.get("sleep_hours") or 7.0)
    hrv_score = float(row.get("hrv_score") or 62.0)
    resting_hr = float(row.get("resting_hr") or 54.0)

    # Acute: distance dominates; calories add secondary load (similar spirit to data_generator coupling)
    acute_load_7d = max(0.05, daily_distance_km * 0.95 + active_cal / 450.0)

    # Chronic: smooth baseline — slightly below acute when load is high, floor for rest days
    chronic_load_21d = max(0.55, acute_load_7d * 0.78 + 1.35)

    ratio = acute_load_7d / chronic_load_21d if chronic_load_21d > 0 else 1.0
    acwr_ratio = float(min(2.8, max(0.35, ratio)))

    # Single-day sleep debt proxy vs 8h target (full rolling(3) unavailable without history)
    sleep_debt_3d = float(max(0.0, (8.0 - sleep_hours) * 1.25))

    # HRV drop proxy: deviation from a notional baseline when only HR/HRV snapshot exists
    baseline_hrv = 62.0
    hrv_drop = float(max(-15.0, min(15.0, baseline_hrv - hrv_score + (resting_hr - 54.0) * 0.15)))

    return {
        "acute_load_7d": acute_load_7d,
        "chronic_load_21d": chronic_load_21d,
        "acwr_ratio": acwr_ratio,
        "sleep_debt_3d": sleep_debt_3d,
        "hrv_drop": hrv_drop,
    }
