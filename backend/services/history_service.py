"""Backward-compatible import path for history services."""

from services.history.repository import (
    fetch_daily_firestore_snapshot,
    fetch_historical_derived_features,
    fetch_user_history,
    get_history_window_context,
    merge_nutrition_with_history,
    save_daily_prediction_result,
    stable_athlete_numeric_id,
)
from services.history.rolling_features import compute_historical_derived_features

__all__ = [
    "compute_historical_derived_features",
    "fetch_daily_firestore_snapshot",
    "fetch_historical_derived_features",
    "fetch_user_history",
    "get_history_window_context",
    "merge_nutrition_with_history",
    "save_daily_prediction_result",
    "stable_athlete_numeric_id",
]
