"""Firestore reads/writes for daily history and predictions."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from config import settings
from schemas.enums import HistoryConfidence
from services.history.date_utils import date_keys_in_range, to_date_key
from services.history.day_quality import count_quality_history_days
from services.history.firestore_client import get_firestore_client
from services.history.history_merge import merge_wake_up_day_row
from services.history.rolling_features import compute_historical_derived_features
from utils.logging import logger


def read_firestore_document(doc_ref: Any) -> Any:
    """Sync Firestore document read (firebase_admin client, not async client)."""
    return doc_ref.get()


def stable_athlete_numeric_id(user_id: str) -> int:
    """Deterministic int id for ML CSV ``athlete_id`` (same uid → same id across runs)."""
    digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
    numeric_id = int(digest[:12], 16) % (2**31 - 1)
    return numeric_id if numeric_id > 0 else 1


def fetch_daily_firestore_snapshot(user_id: str, date_key: str) -> dict[str, Any]:
    """
    Fetch profile + wake-up day health/check-in + prior-day health and nutrition.

    Serve-time merge policy is applied in ``prediction/firestore_mapping``:
    sleep from ``daily_health/{date}``; physical from ``daily_health/{date-1}``;
    survey from ``daily_checkins/{date}``; nutrition from ``daily_nutrition/{date-1}``.
    """
    db = get_firestore_client()
    if db is None:
        return {}
    try:
        user_ref = db.collection("users").document(user_id)
        health_ref = user_ref.collection("daily_health").document(date_key)
        yesterday_key = (to_date_key(date_key) - timedelta(days=1)).strftime("%Y-%m-%d")
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
        user_doc = read_firestore_document(user_ref)
        health_doc = read_firestore_document(health_ref)
        health_yesterday_doc = read_firestore_document(health_yesterday_ref)
        checkin_doc = read_firestore_document(checkin_ref)
        nutrition_yesterday_doc = read_firestore_document(nutrition_yesterday_ref)
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


def save_daily_prediction_result(
    user_id: str,
    date_key: str,
    result: dict[str, Any],
) -> bool:
    """Persist prediction output under users/{uid}/daily_health/{date} using merge."""
    db = get_firestore_client()
    if db is None:
        return False
    try:
        risk_score = float(result.get("risk_score") or 0.0)
        confidence = float(result.get("prediction_confidence") or 0.0)
        doc = {
            "finalRiskScore": round(risk_score * 100.0, 2),
            "riskLevel": result.get("risk_level"),
            "predictionConfidence": round(min(100.0, max(0.0, confidence)), 2),
            "predictionUpdatedAt": datetime.now(timezone.utc).isoformat(),
        }
        db.collection("users").document(user_id).collection("daily_health").document(date_key).set(
            doc,
            merge=True,
        )
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
    Fetch logical wake-up-day history rows for the prediction window.

    Each row is keyed by wake-up day ``W`` and merged like production inference:
    physical from ``daily_health/{W-1}``, sleep from ``daily_health/{W}``,
    survey from ``daily_checkins/{W}``.

    For prediction date ``D`` with ``include_target_day=False`` (rolling features),
    wake-up days are ``D-7 … D-1``; physical docs ``D-8 … D-2`` are read as needed.
    """
    try:
        end_day = to_date_key(date_key)
    except ValueError:
        return []
    if include_target_day:
        start_day = end_day - timedelta(days=lookback_days - 1)
        end_inclusive = end_day
    else:
        end_inclusive = end_day - timedelta(days=1)
        start_day = end_inclusive - timedelta(days=lookback_days - 1)

    db = get_firestore_client()
    if db is None:
        return []

    try:
        user_ref = db.collection("users").document(user_id)
        health_ref = user_ref.collection("daily_health")
        checkin_ref = user_ref.collection("daily_checkins")
    except Exception:
        return []

    merged_rows: list[dict[str, Any]] = []
    for wake_up_key in date_keys_in_range(start_day, end_inclusive):
        physical_key = (to_date_key(wake_up_key) - timedelta(days=1)).strftime("%Y-%m-%d")
        physical_doc = read_firestore_document(health_ref.document(physical_key))
        wake_doc = read_firestore_document(health_ref.document(wake_up_key))
        checkin_doc = read_firestore_document(checkin_ref.document(wake_up_key))
        row = merge_wake_up_day_row(
            wake_up_key,
            physical_doc.to_dict() if physical_doc.exists else None,
            wake_doc.to_dict() if wake_doc.exists else None,
            checkin_doc.to_dict() if checkin_doc.exists else None,
        )
        if row is not None:
            merged_rows.append(row)
    return merged_rows


def history_confidence_from_quality_days(quality_days: int) -> HistoryConfidence:
    if quality_days >= settings.HISTORY_CONFIDENCE_HIGH_MIN_DAYS:
        return HistoryConfidence.HIGH
    if quality_days >= settings.HISTORY_CONFIDENCE_MEDIUM_MIN_DAYS:
        return HistoryConfidence.MEDIUM
    return HistoryConfidence.LOW


def get_history_window_context(
    user_id: str,
    date_key: str,
    lookback_days: int | None = None,
    include_target_day: bool = True,
) -> dict[str, Any]:
    """
    Return historical feature context with quality metadata for fallback decisions.

    confidence policy (see config.settings):
    - high:   HISTORY_CONFIDENCE_HIGH_MIN_DAYS+ usable days
    - medium: HISTORY_CONFIDENCE_MEDIUM_MIN_DAYS .. high-1 usable days
    - low:    below medium threshold

    Each history row is a merged wake-up day (physical@W-1, sleep/survey@W).
    A day is usable when at least three watch-sync signal groups are present
    on that merged row (load, sleep, heart, energy).
    """
    resolved_lookback = (
        settings.HISTORY_LOOKBACK_DAYS if lookback_days is None else lookback_days
    )
    rows = fetch_user_history(
        user_id,
        date_key,
        lookback_days=resolved_lookback,
        include_target_day=include_target_day,
    )
    days_count = len(rows)
    quality_days_count = count_quality_history_days(rows)
    features = compute_historical_derived_features(rows)
    confidence = history_confidence_from_quality_days(quality_days_count)
    return {
        "days_count": days_count,
        "quality_days_count": quality_days_count,
        "confidence": confidence.value,
        "features": features,
        "recent_row": rows[-1] if rows else None,
    }
