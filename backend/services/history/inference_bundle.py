"""Single-batch Firestore load for production inference inputs + history."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from config import settings
from services.history.date_utils import date_keys_in_range, to_date_key
from services.history.firestore_client import get_firestore_client
from services.history.firestore_field_paths import INFERENCE_FIELD_PATHS
from services.history.firestore_io import doc_to_dict, read_firestore_documents
from services.history.history_window import (
    build_history_window_context,
    history_date_window,
    history_rows_from_snapshots,
)
from utils.logging import logger


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
    start_day, end_inclusive = history_date_window(end_day, lookback_days, include_target_day)
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
        "profile": doc_to_dict(snapshot_by_key.get("profile")),
        "daily_health": doc_to_dict(snapshot_by_key.get("health:today")),
        "daily_health_yesterday": doc_to_dict(snapshot_by_key.get("health:yesterday")),
        "daily_checkins": doc_to_dict(snapshot_by_key.get("checkin:today")),
        "daily_nutrition_yesterday": doc_to_dict(snapshot_by_key.get("nutrition:yesterday")),
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
    history_rows = history_rows_from_snapshots(wake_up_keys, snapshot_by_key)
    return {
        "snapshot": _snapshot_dict_from_inference_refs(snapshot_by_key),
        "history_rows": history_rows,
        "history_context": build_history_window_context(history_rows),
    }
