"""Firestore reads/writes for daily history and predictions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from config import settings
from schemas.enums import HistoryConfidence
from services.history.date_utils import date_keys_in_range, to_date_key
from services.history.day_quality import count_quality_history_days
from services.history.firestore_client import get_firestore_client
from services.history.firestore_field_paths import INFERENCE_FIELD_PATHS
from services.history.history_merge import merge_wake_up_day_row
from services.history.rolling_features import compute_historical_derived_features
from utils.logging import logger


def read_firestore_document(doc_ref: Any, field_paths: tuple[str, ...] | None = None) -> Any:
    """Sync Firestore document read (firebase_admin client, not async client)."""
    if field_paths:
        return doc_ref.get(field_paths=field_paths)
    return doc_ref.get()


def read_firestore_documents(
    db: Any,
    doc_refs: list[Any],
    *,
    field_paths: tuple[str, ...] | None = None,
) -> list[Any]:
    """
    Batch-read Firestore documents in one round trip when the client supports ``get_all``.

    When ``field_paths`` is set, only those top-level fields are returned per document.
    Falls back to sequential ``doc_ref.get()`` for tests or minimal mocks without ``get_all``.
    """
    if not doc_refs:
        return []
    get_all = getattr(db, "get_all", None)
    if callable(get_all):
        if field_paths:
            return list(get_all(doc_refs, field_paths=field_paths))
        return list(get_all(doc_refs))
    return [read_firestore_document(ref, field_paths=field_paths) for ref in doc_refs]


def _queue_unique_ref(
    ref_entries: list[tuple[str, Any]],
    seen_cache_keys: set[str],
    cache_key: str,
    doc_ref: Any,
) -> None:
    if cache_key in seen_cache_keys:
        return
    seen_cache_keys.add(cache_key)
    ref_entries.append((cache_key, doc_ref))


def _build_inference_ref_entries(
    user_ref: Any,
    date_key: str,
    *,
    lookback_days: int,
    include_target_day: bool,
) -> tuple[list[tuple[str, Any]], list[str]]:
    """Collect deduplicated Firestore refs for snapshot + wake-up-day history."""
    end_day = to_date_key(date_key)
    yesterday_key = (end_day - timedelta(days=1)).strftime("%Y-%m-%d")
    start_day, end_inclusive = _history_date_window(end_day, lookback_days, include_target_day)
    wake_up_keys = date_keys_in_range(start_day, end_inclusive)

    health_ref = user_ref.collection("daily_health")
    checkin_ref = user_ref.collection("daily_checkins")
    ref_entries: list[tuple[str, Any]] = []
    seen_cache_keys: set[str] = set()

    _queue_unique_ref(ref_entries, seen_cache_keys, "profile", user_ref)
    _queue_unique_ref(ref_entries, seen_cache_keys, "health:today", health_ref.document(date_key))
    _queue_unique_ref(
        ref_entries,
        seen_cache_keys,
        "health:yesterday",
        health_ref.document(yesterday_key),
    )
    _queue_unique_ref(ref_entries, seen_cache_keys, "checkin:today", checkin_ref.document(date_key))
    _queue_unique_ref(
        ref_entries,
        seen_cache_keys,
        "nutrition:yesterday",
        user_ref.collection("daily_nutrition").document(yesterday_key),
    )

    for wake_up_key in wake_up_keys:
        physical_key = (to_date_key(wake_up_key) - timedelta(days=1)).strftime("%Y-%m-%d")
        _queue_unique_ref(ref_entries, seen_cache_keys, f"health:{physical_key}", health_ref.document(physical_key))
        _queue_unique_ref(ref_entries, seen_cache_keys, f"health:{wake_up_key}", health_ref.document(wake_up_key))
        _queue_unique_ref(ref_entries, seen_cache_keys, f"checkin:{wake_up_key}", checkin_ref.document(wake_up_key))

    return ref_entries, wake_up_keys


def _snapshot_dict_from_inference_refs(
    snapshot_by_key: dict[str, Any],
) -> dict[str, Any]:
    return {
        "profile": _doc_dict(snapshot_by_key.get("profile")),
        "daily_health": _doc_dict(snapshot_by_key.get("health:today")),
        "daily_health_yesterday": _doc_dict(snapshot_by_key.get("health:yesterday")),
        "daily_checkins": _doc_dict(snapshot_by_key.get("checkin:today")),
        "daily_nutrition_yesterday": _doc_dict(snapshot_by_key.get("nutrition:yesterday")),
    }


def _doc_dict(snapshot: Any | None) -> dict[str, Any]:
    if snapshot is None or not snapshot.exists:
        return {}
    return snapshot.to_dict() or {}


def _history_rows_from_inference_refs(
    wake_up_keys: list[str],
    snapshot_by_key: dict[str, Any],
) -> list[dict[str, Any]]:
    merged_rows: list[dict[str, Any]] = []
    for wake_up_key in wake_up_keys:
        physical_key = (to_date_key(wake_up_key) - timedelta(days=1)).strftime("%Y-%m-%d")
        physical_doc = snapshot_by_key.get(f"health:{physical_key}")
        wake_doc = snapshot_by_key.get(f"health:{wake_up_key}")
        checkin_doc = snapshot_by_key.get(f"checkin:{wake_up_key}")
        row = merge_wake_up_day_row(
            wake_up_key,
            _doc_dict(physical_doc) or None,
            _doc_dict(wake_doc) or None,
            _doc_dict(checkin_doc) or None,
        )
        if row is not None:
            merged_rows.append(row)
    return merged_rows


def build_history_window_context(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive rolling features and confidence metadata from merged history rows."""
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


def fetch_inference_firestore_bundle(
    user_id: str,
    date_key: str,
    *,
    lookback_days: int | None = None,
    include_target_day: bool = False,
) -> dict[str, Any]:
    """
    Single batch read for production inference: snapshot inputs + history window.

    Uses ``INFERENCE_FIELD_PATHS`` so prediction outputs (``finalRiskScore``, ``aiRecommendation``,
    etc.) and unrelated profile fields are not transferred.
    """
    db = get_firestore_client()
    if db is None:
        return {}

    resolved_lookback = (
        settings.HISTORY_LOOKBACK_DAYS if lookback_days is None else lookback_days
    )
    try:
        user_ref = db.collection("users").document(user_id)
        ref_entries, wake_up_keys = _build_inference_ref_entries(
            user_ref,
            date_key,
            lookback_days=resolved_lookback,
            include_target_day=include_target_day,
        )
        snapshots = read_firestore_documents(
            db,
            [doc_ref for _, doc_ref in ref_entries],
            field_paths=INFERENCE_FIELD_PATHS,
        )
    except Exception as exc:
        logger.warning(
            "fetch_inference_firestore_bundle failed for user_id=%s date=%s: %s",
            user_id,
            date_key,
            exc,
            exc_info=True,
        )
        return {}

    snapshot_by_key = {
        cache_key: snapshots[index]
        for index, (cache_key, _) in enumerate(ref_entries)
    }
    history_rows = _history_rows_from_inference_refs(wake_up_keys, snapshot_by_key)
    return {
        "snapshot": _snapshot_dict_from_inference_refs(snapshot_by_key),
        "history_rows": history_rows,
        "history_context": build_history_window_context(history_rows),
    }


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
        (
            user_doc,
            health_doc,
            health_yesterday_doc,
            checkin_doc,
            nutrition_yesterday_doc,
        ) = read_firestore_documents(
            db,
            [
                user_ref,
                health_ref,
                health_yesterday_ref,
                checkin_ref,
                nutrition_yesterday_ref,
            ],
            field_paths=INFERENCE_FIELD_PATHS,
        )
    except Exception as exc:
        logger.warning(
            "fetch_daily_firestore_snapshot failed for user_id=%s date=%s: %s",
            user_id,
            date_key,
            exc,
            exc_info=True,
        )
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
    except Exception as exc:
        logger.warning(
            "save_daily_prediction_result failed for user_id=%s date=%s: %s",
            user_id,
            date_key,
            exc,
            exc_info=True,
        )
        return False


def _history_date_window(
    end_day: datetime,
    lookback_days: int,
    include_target_day: bool,
) -> tuple[datetime, datetime]:
    """Return inclusive [start_day, end_inclusive] for wake-up-day history fetches.

    Example: prediction date D, lookback 7, exclude target → wake-up days D-7 … D-1.
    """
    if include_target_day:
        start_day = end_day - timedelta(days=lookback_days - 1)
        end_inclusive = end_day
    else:
        end_inclusive = end_day - timedelta(days=1)
        start_day = end_inclusive - timedelta(days=lookback_days - 1)
    return start_day, end_inclusive


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
    start_day, end_inclusive = _history_date_window(end_day, lookback_days, include_target_day)

    db = get_firestore_client()
    if db is None:
        return []

    try:
        user_ref = db.collection("users").document(user_id)
        health_ref = user_ref.collection("daily_health")
        checkin_ref = user_ref.collection("daily_checkins")
    except Exception as exc:
        logger.warning(
            "fetch_user_history client setup failed for user_id=%s date=%s: %s",
            user_id,
            date_key,
            exc,
            exc_info=True,
        )
        return []

    wake_up_keys = date_keys_in_range(start_day, end_inclusive)
    ref_entries: list[tuple[str, Any]] = []
    seen_cache_keys: set[str] = set()

    def _queue_ref(cache_key: str, doc_ref: Any) -> None:
        if cache_key in seen_cache_keys:
            return
        seen_cache_keys.add(cache_key)
        ref_entries.append((cache_key, doc_ref))

    for wake_up_key in wake_up_keys:
        physical_key = (to_date_key(wake_up_key) - timedelta(days=1)).strftime("%Y-%m-%d")
        _queue_ref(f"health:{physical_key}", health_ref.document(physical_key))
        _queue_ref(f"health:{wake_up_key}", health_ref.document(wake_up_key))
        _queue_ref(f"checkin:{wake_up_key}", checkin_ref.document(wake_up_key))

    try:
        snapshots = read_firestore_documents(
            db,
            [doc_ref for _, doc_ref in ref_entries],
            field_paths=INFERENCE_FIELD_PATHS,
        )
    except Exception as exc:
        logger.warning(
            "fetch_user_history batch read failed for user_id=%s date=%s: %s",
            user_id,
            date_key,
            exc,
            exc_info=True,
        )
        return []

    snapshot_by_key = {
        cache_key: snapshots[index]
        for index, (cache_key, _) in enumerate(ref_entries)
    }

    merged_rows: list[dict[str, Any]] = []
    for wake_up_key in wake_up_keys:
        physical_key = (to_date_key(wake_up_key) - timedelta(days=1)).strftime("%Y-%m-%d")
        physical_doc = snapshot_by_key[f"health:{physical_key}"]
        wake_doc = snapshot_by_key[f"health:{wake_up_key}"]
        checkin_doc = snapshot_by_key[f"checkin:{wake_up_key}"]
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
    return build_history_window_context(rows)
