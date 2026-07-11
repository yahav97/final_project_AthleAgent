"""Wake-up-day history window, rolling context, and confidence bands."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from config import settings
from schemas.enums import HistoryConfidence
from services.history.date_utils import date_keys_in_range, to_date_key
from services.history.day_quality import count_quality_history_days
from services.history.firestore_client import get_firestore_client
from services.history.firestore_field_paths import INFERENCE_FIELD_PATHS
from services.history.firestore_io import doc_to_dict, read_firestore_documents
from services.history.history_merge import merge_wake_up_day_row
from services.history.rolling_features import compute_historical_derived_features
from utils.logging import logger


def history_date_window(
    end_day: datetime,
    lookback_days: int,
    include_target_day: bool,
) -> tuple[datetime, datetime]:
    """Return inclusive ``[start_day, end_inclusive]`` for wake-up-day history fetches.

    Example: prediction date D, lookback 7, exclude target → wake-up days D-7 … D-1.
    """
    if include_target_day:
        start_day = end_day - timedelta(days=lookback_days - 1)
        end_inclusive = end_day
    else:
        end_inclusive = end_day - timedelta(days=1)
        start_day = end_inclusive - timedelta(days=lookback_days - 1)
    return start_day, end_inclusive


def history_confidence_from_quality_days(quality_days: int) -> HistoryConfidence:
    if quality_days >= settings.HISTORY_CONFIDENCE_HIGH_MIN_DAYS:
        return HistoryConfidence.HIGH
    if quality_days >= settings.HISTORY_CONFIDENCE_MEDIUM_MIN_DAYS:
        return HistoryConfidence.MEDIUM
    return HistoryConfidence.LOW


def history_rows_from_snapshots(
    wake_up_keys: list[str],
    snapshot_by_key: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build merged wake-up-day rows from a ``health:*`` / ``checkin:*`` snapshot map."""
    merged_rows: list[dict[str, Any]] = []
    for wake_up_key in wake_up_keys:
        physical_key = (to_date_key(wake_up_key) - timedelta(days=1)).strftime("%Y-%m-%d")
        row = merge_wake_up_day_row(
            wake_up_key,
            doc_to_dict(snapshot_by_key.get(f"health:{physical_key}")) or None,
            doc_to_dict(snapshot_by_key.get(f"health:{wake_up_key}")) or None,
            doc_to_dict(snapshot_by_key.get(f"checkin:{wake_up_key}")) or None,
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
    start_day, end_inclusive = history_date_window(end_day, lookback_days, include_target_day)

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
    return history_rows_from_snapshots(wake_up_keys, snapshot_by_key)


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
