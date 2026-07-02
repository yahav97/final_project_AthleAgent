"""Per-day signal checks for history-window confidence."""

from __future__ import annotations

from typing import Any

from config import settings
from services.preprocessing.helpers import is_absent_or_weak

# Alternative Firestore / API field names for one wearable signal category.
WatchSyncFieldNames = tuple[str, ...]

# Evaluated on merged wake-up-day rows (physical@W-1, sleep@W) from fetch_user_history.
LOAD_FIELD_NAMES: WatchSyncFieldNames = (
    "distanceMeters",
    "distance_meters",
    "daily_distance_meters",
    "steps",
    "daily_steps",
)
SLEEP_FIELD_NAMES: WatchSyncFieldNames = ("sleepMinutes", "sleep_minutes")
HEART_FIELD_NAMES: WatchSyncFieldNames = (
    "heartRateAvg",
    "avgHeartRate",
    "heart_rate_avg",
    "restingHeartRate",
    "resting_heart_rate",
    "resting_hr",
    "hrvRmssd",
    "hrv_rmssd",
    "hrv_score",
)
ENERGY_FIELD_NAMES: WatchSyncFieldNames = (
    "activeCalories",
    "active_calories",
    "active_calories_burned",
    "totalCalories",
    "total_calories",
    "daily_calories",
    "bmrCalories",
    "bmr_calories",
)

# Named categories → field-name aliases. Threshold from settings.HISTORY_MIN_WATCH_SYNC_SIGNAL_GROUPS.
WATCH_SYNC_SIGNAL_GROUPS: dict[str, WatchSyncFieldNames] = {
    "load": LOAD_FIELD_NAMES,
    "sleep": SLEEP_FIELD_NAMES,
    "heart": HEART_FIELD_NAMES,
    "energy": ENERGY_FIELD_NAMES,
}


def min_watch_sync_signal_groups_required() -> int:
    return settings.HISTORY_MIN_WATCH_SYNC_SIGNAL_GROUPS


def _row_has_any_usable_field(row: dict[str, Any], field_names: WatchSyncFieldNames) -> bool:
    return any(not is_absent_or_weak(row.get(name)) for name in field_names)


def count_watch_sync_signal_groups(row: dict[str, Any]) -> int:
    """How many watch-sync categories (load, sleep, heart, energy) have usable values."""
    return sum(
        1
        for field_names in WATCH_SYNC_SIGNAL_GROUPS.values()
        if _row_has_any_usable_field(row, field_names)
    )


def is_quality_history_day(row: dict[str, Any]) -> bool:
    """Day counts toward history confidence when it looks like a real wearable sync."""
    return count_watch_sync_signal_groups(row) >= min_watch_sync_signal_groups_required()


def count_quality_history_days(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows if is_quality_history_day(row))
