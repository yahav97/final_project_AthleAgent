"""Firestore history fetch + rolling feature computation for prediction."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pandas as pd


def _to_date_key(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def _daily_distance_km(doc: dict[str, Any]) -> float:
    distance_m = float(doc.get("distanceMeters") or 0.0)
    if distance_m > 0:
        return distance_m / 1000.0
    steps = float(doc.get("steps") or 0.0)
    return max(0.0, steps * 0.0008)


def _sleep_hours(doc: dict[str, Any]) -> float:
    sleep_minutes = float(doc.get("sleepMinutes") or 0.0)
    if sleep_minutes <= 0:
        return 7.0
    return max(3.0, min(12.0, sleep_minutes / 60.0))


def _resting_hr(doc: dict[str, Any]) -> float:
    hr_min = float(doc.get("heartRateMin") or 0.0)
    hr_avg = float(doc.get("heartRateAvg") or 0.0)
    if hr_min > 0:
        return max(38.0, min(95.0, hr_min))
    if hr_avg > 0:
        return max(38.0, min(95.0, hr_avg))
    return 54.0


def _hrv_proxy_from_resting_hr(resting_hr: float) -> float:
    return float(max(30.0, min(100.0, 110.0 - resting_hr * 0.65)))


def compute_historical_derived_features(history_rows: list[dict[str, Any]]) -> dict[str, float] | None:
    """
    Compute training-style rolling features from merged daily history rows.

    Expected keys in each row:
    - date_key (yyyy-MM-dd)
    - distanceMeters / steps
    - sleepMinutes
    - heartRateMin / heartRateAvg
    """
    if not history_rows:
        return None

    rows: list[dict[str, float | str]] = []
    for row in history_rows:
        date_key = str(row.get("date_key") or "")
        if not date_key:
            continue
        rest_hr = _resting_hr(row)
        hrv_score = _hrv_proxy_from_resting_hr(rest_hr)
        rows.append(
            {
                "date_key": date_key,
                "daily_distance_km": _daily_distance_km(row),
                "sleep_hours": _sleep_hours(row),
                "hrv_score": hrv_score,
            }
        )
    if not rows:
        return None

    df = pd.DataFrame(rows).sort_values("date_key")
    df["acute_load_7d"] = df["daily_distance_km"].rolling(7, min_periods=1).mean()
    df["chronic_load_21d"] = df["daily_distance_km"].rolling(21, min_periods=1).mean()
    df["acwr_ratio"] = df["acute_load_7d"] / df["chronic_load_21d"].replace(0, pd.NA)
    df["acwr_ratio"] = df["acwr_ratio"].fillna(1.0).clip(lower=0.35, upper=2.8)

    # Match training generator semantics: allow negative sleep debt contributions.
    df["sleep_debt_3d"] = (8.0 - df["sleep_hours"]).rolling(3, min_periods=1).sum()
    df["hrv_rolling_7d"] = df["hrv_score"].rolling(7, min_periods=1).mean()
    df["hrv_drop"] = (df["hrv_score"] - df["hrv_rolling_7d"]).clip(lower=-15.0, upper=15.0)

    latest = df.iloc[-1]
    return {
        "acute_load_7d": float(latest["acute_load_7d"]),
        "chronic_load_21d": float(latest["chronic_load_21d"]),
        "acwr_ratio": float(latest["acwr_ratio"]),
        "sleep_debt_3d": float(latest["sleep_debt_3d"]),
        "hrv_drop": float(latest["hrv_drop"]),
    }


def fetch_historical_derived_features(user_id: str, date_key: str, lookback_days: int = 21) -> dict[str, float] | None:
    """
    Pull historical daily docs from Firestore and compute rolling features.

    Returns None if Firestore SDK/credentials are unavailable or data is insufficient.
    """
    try:
        from google.cloud import firestore  # lazy import; optional at runtime
    except Exception:
        return None

    try:
        end_day = _to_date_key(date_key)
    except ValueError:
        return None
    start_day = end_day - timedelta(days=lookback_days - 1)

    try:
        db = firestore.Client()
        user_ref = db.collection("users").document(user_id)
        health_docs = user_ref.collection("daily_health").stream()
        checkin_docs = user_ref.collection("daily_checkins").stream()
    except Exception:
        return None

    health_by_date: dict[str, dict[str, Any]] = {}
    for doc in health_docs:
        key = doc.id
        try:
            d = _to_date_key(key)
        except ValueError:
            continue
        if start_day <= d <= end_day:
            health_by_date[key] = doc.to_dict() or {}

    checkin_by_date: dict[str, dict[str, Any]] = {}
    for doc in checkin_docs:
        key = doc.id
        try:
            d = _to_date_key(key)
        except ValueError:
            continue
        if start_day <= d <= end_day:
            checkin_by_date[key] = doc.to_dict() or {}

    merged_rows: list[dict[str, Any]] = []
    for key in sorted(health_by_date.keys()):
        row = dict(health_by_date.get(key) or {})
        row.update(checkin_by_date.get(key) or {})
        row["date_key"] = key
        merged_rows.append(row)

    return compute_historical_derived_features(merged_rows)
