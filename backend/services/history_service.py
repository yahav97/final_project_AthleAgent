"""History repository + rolling feature engineering from Firestore."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from config import settings


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
    """Compute weekly-history rolling features from merged historical daily rows."""
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
    # Weekly history policy:
    # - acute uses true 7-day mean load
    # - chronic (feature name kept for model compatibility) is approximated from
    #   the weekly baseline because only 7 days are retained.
    df["acute_load_7d"] = df["daily_distance_km"].rolling(7, min_periods=1).mean()
    weekly_mean = df["daily_distance_km"].rolling(7, min_periods=1).mean()
    weekly_std = df["daily_distance_km"].rolling(7, min_periods=1).std().fillna(0.0)
    df["chronic_load_21d"] = (weekly_mean * 0.85 + weekly_std * 0.35 + 0.5).clip(lower=0.55)
    df["acwr_ratio"] = df["acute_load_7d"] / df["chronic_load_21d"].replace(0, pd.NA)
    df["acwr_ratio"] = df["acwr_ratio"].fillna(1.0).clip(lower=0.35, upper=2.8)

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


def _get_firestore_client():
    """Initialize Firebase Admin SDK and return Firestore client."""
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except Exception:
        return None

    if not firebase_admin._apps:
        cred_path = settings.FIREBASE_SERVICE_ACCOUNT_KEY or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        try:
            if cred_path:
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
            else:
                firebase_admin.initialize_app()
        except Exception:
            return None
    try:
        return firestore.client()
    except Exception:
        return None


def fetch_user_history(user_id: str, date_key: str, lookback_days: int = 7) -> list[dict[str, Any]]:
    """
    Repository layer: fetch merged daily history rows for user/date window.

    Returns list of daily dict rows sorted by date_key.
    """
    try:
        end_day = _to_date_key(date_key)
    except ValueError:
        return []
    start_day = end_day - timedelta(days=lookback_days - 1)

    db = _get_firestore_client()
    if db is None:
        return []

    try:
        user_ref = db.collection("users").document(user_id)
        health_docs = user_ref.collection("daily_health").stream()
        checkin_docs = user_ref.collection("daily_checkins").stream()
    except Exception:
        return []

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
    return merged_rows


def fetch_historical_derived_features(user_id: str, date_key: str, lookback_days: int = 7) -> dict[str, float] | None:
    rows = fetch_user_history(user_id, date_key, lookback_days=lookback_days)
    return compute_historical_derived_features(rows)


def get_history_window_context(user_id: str, date_key: str, lookback_days: int = 7) -> dict[str, Any]:
    """
    Return historical feature context with quality metadata for fallback decisions.

    confidence policy:
    - high: 7 days
    - medium: 4-6 days
    - low: 0-3 days
    """
    rows = fetch_user_history(user_id, date_key, lookback_days=lookback_days)
    days_count = len(rows)
    features = compute_historical_derived_features(rows)
    if days_count >= 7:
        confidence = "high"
    elif days_count >= 4:
        confidence = "medium"
    else:
        confidence = "low"
    return {
        "days_count": days_count,
        "confidence": confidence,
        "features": features,
    }
