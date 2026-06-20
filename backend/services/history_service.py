"""History repository + rolling feature engineering from Firestore."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from config import settings
from services.field_transforms import (
    daily_distance_km_from_doc,
    hrv_proxy_from_resting_hr,
    injured_yesterday_from_doc,
    resting_hr_from_doc,
)
from utils.logging import logger


def _to_date_key(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def _date_keys_in_range(start_day: datetime, end_day: datetime) -> list[str]:
    keys: list[str] = []
    day = start_day
    while day <= end_day:
        keys.append(day.strftime("%Y-%m-%d"))
        day += timedelta(days=1)
    return keys


def _sleep_hours(doc: dict[str, Any]) -> float:
    sleep_minutes = float(doc.get("sleepMinutes") or 0.0)
    if sleep_minutes <= 0:
        return 7.0
    return max(3.0, min(12.0, sleep_minutes / 60.0))


def _hrv_score(doc: dict[str, Any], resting_hr: float) -> float:
    hrv_rmssd = float(doc.get("hrvRmssd") or 0.0)
    if hrv_rmssd > 0:
        return float(max(30.0, min(105.0, hrv_rmssd)))
    return hrv_proxy_from_resting_hr(resting_hr)


def compute_historical_derived_features(history_rows: list[dict[str, Any]]) -> dict[str, float] | None:
    """Compute weekly-history rolling features from merged historical daily rows."""
    if not history_rows:
        return None

    rows: list[dict[str, float | str]] = []
    for row in history_rows:
        date_key = str(row.get("date_key") or "")
        if not date_key:
            continue
        rest_hr = resting_hr_from_doc(row)
        hrv_score = _hrv_score(row, rest_hr)
        rows.append(
            {
                "date_key": date_key,
                "daily_distance_km": daily_distance_km_from_doc(row),
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
        cred_path = settings.FIREBASE_SERVICE_ACCOUNT_KEY or settings.GOOGLE_APPLICATION_CREDENTIALS
        try:
            if cred_path:
                cred = credentials.Certificate(str(cred_path))
                firebase_admin.initialize_app(cred)
            else:
                firebase_admin.initialize_app()
        except Exception:
            return None
    try:
        return firestore.client()
    except Exception:
        return None


def stable_athlete_numeric_id(user_id: str) -> int:
    """Deterministic int id for ML CSV ``athlete_id`` (same uid → same id across runs)."""
    h = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
    n = int(h[:12], 16) % (2**31 - 1)
    return n if n > 0 else 1


def fetch_injury_tomorrow_label(user_id: str, date_key: str) -> int | None:
    """
    Label for training row ``(user_id, date_key)``:

    On ``users/{uid}/daily_checkins/{D+1}``, ``injuredYesterday`` indicates injury on calendar day ``D``.
    Falls back to the same field on ``daily_health/{D+1}`` for legacy data.

    Returns:
        ``0`` or ``1`` when the next-day check-in (or legacy health doc) exists.
        ``None`` when neither next-day document exists (caller should skip).
    """
    db = _get_firestore_client()
    if db is None:
        return None
    try:
        next_key = (_to_date_key(date_key) + timedelta(days=1)).strftime("%Y-%m-%d")
        user_ref = db.collection("users").document(user_id)
        checkin_doc = user_ref.collection("daily_checkins").document(next_key).get()
        if checkin_doc.exists:
            parsed = injured_yesterday_from_doc(checkin_doc.to_dict() or {})
            return 0 if parsed is None else parsed
        health_doc = user_ref.collection("daily_health").document(next_key).get()
    except Exception:
        logger.exception("fetch_injury_tomorrow_label failed user_id=%s date=%s", user_id, date_key)
        return None
    if not health_doc.exists:
        return None
    parsed = injured_yesterday_from_doc(health_doc.to_dict() or {})
    if parsed is not None:
        return parsed
    return 0


def fetch_daily_firestore_snapshot(user_id: str, date_key: str) -> dict[str, Any]:
    """
    Fetch profile + wake-up day health/check-in + prior-day health and nutrition.

    Serve-time merge policy is applied in ``prediction_service``:
    sleep from ``daily_health/{date}``; physical from ``daily_health/{date-1}``;
    survey from ``daily_checkins/{date}``; nutrition from ``daily_nutrition/{date-1}``.
    """
    db = _get_firestore_client()
    if db is None:
        return {}
    try:
        user_ref = db.collection("users").document(user_id)
        health_ref = user_ref.collection("daily_health").document(date_key)
        yesterday_key = (_to_date_key(date_key) - timedelta(days=1)).strftime("%Y-%m-%d")
        health_yesterday_ref = user_ref.collection("daily_health").document(yesterday_key)
        checkin_ref = user_ref.collection("daily_checkins").document(date_key)
        nutrition_yesterday_ref = user_ref.collection("daily_nutrition").document(yesterday_key)
        logger.info(
            "fetch_daily_firestore_snapshot paths: profile=%s daily_health=%s daily_health_yesterday=%s "
            "daily_checkins=%s daily_nutrition_yesterday=%s",
            user_ref.path,
            health_ref.path,
            health_yesterday_ref.path,
            checkin_ref.path,
            nutrition_yesterday_ref.path,
        )
        user_doc = user_ref.get()
        health_doc = health_ref.get()
        health_yesterday_doc = health_yesterday_ref.get()
        checkin_doc = checkin_ref.get()
        nutrition_yesterday_doc = nutrition_yesterday_ref.get()
    except Exception:
        return {}

    return {
        "profile": user_doc.to_dict() if user_doc.exists else {},
        "daily_health": health_doc.to_dict() if health_doc.exists else {},
        "daily_health_yesterday": health_yesterday_doc.to_dict() if health_yesterday_doc.exists else {},
        "daily_checkins": checkin_doc.to_dict() if checkin_doc.exists else {},
        "daily_nutrition_yesterday": (
            nutrition_yesterday_doc.to_dict() if nutrition_yesterday_doc.exists else {}
        ),
    }


def merge_nutrition_with_history(user_id: str, date_key: str, primary: dict[str, Any]) -> dict[str, Any]:
    """
    Fill missing nutrition aggregates from recent prior days (same user).

    For morning prediction on wake-up day ``D``, pass ``primary`` from ``daily_nutrition/{D-1}``
    and ``date_key=D`` so backfill scans ``D-2``, ``D-3``, … when yesterday is incomplete.

    Only nutrition fields may be backfilled from history; load/recovery come from the client.
    """
    out = dict(primary or {})
    keys = ("totalProtein", "totalCarbs", "mealsLoggedCount", "totalCalories")

    def field_missing(k: str) -> bool:
        return out.get(k) is None

    if not any(field_missing(k) for k in keys):
        return out

    db = _get_firestore_client()
    if db is None:
        return out
    try:
        base = _to_date_key(date_key)
        user_ref = db.collection("users").document(user_id)
        for i in range(1, 15):
            dk = (base - timedelta(days=i)).strftime("%Y-%m-%d")
            doc = user_ref.collection("daily_nutrition").document(dk).get()
            if not doc.exists:
                continue
            prev = doc.to_dict() or {}
            for k in keys:
                if field_missing(k) and prev.get(k) is not None:
                    out[k] = prev[k]
            if not any(field_missing(k) for k in keys):
                break
    except Exception:
        logger.exception("merge_nutrition_with_history failed user_id=%s date=%s", user_id, date_key)
    return out


def save_daily_prediction_result(
    user_id: str,
    date_key: str,
    result: dict[str, Any],
) -> bool:
    """
    Persist prediction output under users/{uid}/daily_health/{date} using merge.
    """
    db = _get_firestore_client()
    if db is None:
        return False
    try:
        risk_score = float(result.get("risk_score") or 0.0)
        conf = float(result.get("prediction_confidence") or 0.0)
        doc = {
            "finalRiskScore": round(risk_score * 100.0, 2),
            "riskLevel": result.get("risk_level"),
            "predictionConfidence": round(min(100.0, max(0.0, conf)), 2),
            "predictionUpdatedAt": datetime.now(timezone.utc).isoformat(),
        }
        db.collection("users").document(user_id).collection("daily_health").document(date_key).set(doc, merge=True)
        return True
    except Exception:
        return False


def fetch_user_history(
    user_id: str,
    date_key: str,
    lookback_days: int = 7,
    include_target_day: bool = True,
) -> list[dict[str, Any]]:
    """
    Repository layer: fetch merged daily history rows for user/date window.

    Returns list of daily dict rows sorted by date_key.
    """
    try:
        end_day = _to_date_key(date_key)
    except ValueError:
        return []
    if include_target_day:
        start_day = end_day - timedelta(days=lookback_days - 1)
        end_inclusive = end_day
    else:
        end_inclusive = end_day - timedelta(days=1)
        start_day = end_inclusive - timedelta(days=lookback_days - 1)

    db = _get_firestore_client()
    if db is None:
        return []

    try:
        user_ref = db.collection("users").document(user_id)
        health_ref = user_ref.collection("daily_health")
        checkin_ref = user_ref.collection("daily_checkins")
    except Exception:
        return []

    merged_rows: list[dict[str, Any]] = []
    for key in _date_keys_in_range(start_day, end_inclusive):
        health_doc = health_ref.document(key).get()
        if not health_doc.exists:
            continue
        row = dict(health_doc.to_dict() or {})
        checkin_doc = checkin_ref.document(key).get()
        if checkin_doc.exists:
            row.update(checkin_doc.to_dict() or {})
        row["date_key"] = key
        merged_rows.append(row)
    return merged_rows


def fetch_historical_derived_features(
    user_id: str,
    date_key: str,
    lookback_days: int = 7,
    include_target_day: bool = True,
) -> dict[str, float] | None:
    rows = fetch_user_history(
        user_id,
        date_key,
        lookback_days=lookback_days,
        include_target_day=include_target_day,
    )
    return compute_historical_derived_features(rows)


def get_history_window_context(
    user_id: str,
    date_key: str,
    lookback_days: int = 7,
    include_target_day: bool = True,
) -> dict[str, Any]:
    """
    Return historical feature context with quality metadata for fallback decisions.

    confidence policy:
    - high: 7 days
    - medium: 4-6 days
    - low: 0-3 days
    """
    rows = fetch_user_history(
        user_id,
        date_key,
        lookback_days=lookback_days,
        include_target_day=include_target_day,
    )
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
        "recent_row": rows[-1] if rows else None,
    }
