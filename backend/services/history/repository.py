"""Firestore reads/writes for daily history and predictions."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from schemas.enums import HistoryConfidence
from services.history.date_utils import date_keys_in_range, to_date_key
from services.field_transforms import injured_yesterday_from_doc
from services.history.rolling_features import compute_historical_derived_features
from utils.logging import logger


def _firestore_client():
    """Resolve client at call time so tests can monkeypatch services.history_service."""
    import services.history_service as history_service_module

    return history_service_module._get_firestore_client()


def stable_athlete_numeric_id(user_id: str) -> int:
    """Deterministic int id for ML CSV ``athlete_id`` (same uid → same id across runs)."""
    digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
    numeric_id = int(digest[:12], 16) % (2**31 - 1)
    return numeric_id if numeric_id > 0 else 1


def fetch_injury_tomorrow_label(user_id: str, date_key: str) -> int | None:
    """
    Label for training row ``(user_id, date_key)``.

    On ``users/{uid}/daily_checkins/{D+1}``, ``injuredYesterday`` indicates injury on calendar day ``D``.
    Falls back to the same field on ``daily_health/{D+1}`` for legacy data.
    """
    db = _firestore_client()
    if db is None:
        return None
    try:
        next_key = (to_date_key(date_key) + timedelta(days=1)).strftime("%Y-%m-%d")
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
    db = _firestore_client()
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
    Fill missing nutrition aggregates from population averages.

    Uses ``primary`` from ``daily_nutrition/{D-1}`` when present. Missing fields get
    stable baseline values (not a multi-day Firestore backfill), so new athletes are
    not imputed from empty or unrelated prior days.

    ``user_id`` and ``date_key`` are kept for call-site compatibility.
    """
    from services.nutrition_defaults import apply_nutrition_population_defaults

    _ = user_id
    _ = date_key
    return apply_nutrition_population_defaults(primary)


def save_daily_prediction_result(
    user_id: str,
    date_key: str,
    result: dict[str, Any],
) -> bool:
    """Persist prediction output under users/{uid}/daily_health/{date} using merge."""
    db = _firestore_client()
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
    """Repository layer: fetch merged daily history rows for user/date window."""
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

    db = _firestore_client()
    if db is None:
        return []

    try:
        user_ref = db.collection("users").document(user_id)
        health_ref = user_ref.collection("daily_health")
        checkin_ref = user_ref.collection("daily_checkins")
    except Exception:
        return []

    merged_rows: list[dict[str, Any]] = []
    for key in date_keys_in_range(start_day, end_inclusive):
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
    import services.history_service as history_service_module

    rows = history_service_module.fetch_user_history(
        user_id,
        date_key,
        lookback_days=lookback_days,
        include_target_day=include_target_day,
    )
    days_count = len(rows)
    features = compute_historical_derived_features(rows)
    if days_count >= 7:
        confidence = HistoryConfidence.HIGH
    elif days_count >= 4:
        confidence = HistoryConfidence.MEDIUM
    else:
        confidence = HistoryConfidence.LOW
    return {
        "days_count": days_count,
        "confidence": confidence.value,
        "features": features,
        "recent_row": rows[-1] if rows else None,
    }
