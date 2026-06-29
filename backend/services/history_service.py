"""Backward-compatible import path for history services."""

from services.history.date_utils import to_date_key as _to_date_key
from services.history.firestore_client import get_firestore_client as _get_firestore_client
from services.history.repository import (
    fetch_daily_firestore_snapshot,
    fetch_historical_derived_features,
    fetch_injury_today_label,
    fetch_user_history,
    get_history_window_context,
    merge_nutrition_with_history,
    save_daily_prediction_result,
    stable_athlete_numeric_id,
)
from services.history.rolling_features import (
    compute_historical_derived_features,
    hrv_score as _hrv_score,
    sleep_hours as _sleep_hours,
)

__all__ = [
    "_get_firestore_client",
    "_hrv_score",
    "_sleep_hours",
    "_to_date_key",
    "compute_historical_derived_features",
    "fetch_daily_firestore_snapshot",
    "fetch_historical_derived_features",
    "fetch_injury_today_label",
    "fetch_user_history",
    "get_history_window_context",
    "merge_nutrition_with_history",
    "save_daily_prediction_result",
    "stable_athlete_numeric_id",
]
