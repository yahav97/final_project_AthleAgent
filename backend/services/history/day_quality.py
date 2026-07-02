"""Per-day signal checks for history-window confidence."""

from __future__ import annotations

from typing import Any

from services.preprocessing.helpers import is_absent_or_weak

# Evaluated on merged wake-up-day rows (physical@W-1, sleep@W) from fetch_user_history.
SYNC_LOAD_FIELDS: tuple[str, ...] = (
    "distanceMeters",
    "distance_meters",
    "daily_distance_meters",
    "steps",
    "daily_steps",
)
SYNC_SLEEP_FIELDS: tuple[str, ...] = ("sleepMinutes", "sleep_minutes")
SYNC_HEART_FIELDS: tuple[str, ...] = (
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
SYNC_ENERGY_FIELDS: tuple[str, ...] = (
    "activeCalories",
    "active_calories",
    "active_calories_burned",
    "totalCalories",
    "total_calories",
    "daily_calories",
    "bmrCalories",
    "bmr_calories",
)

SYNC_SIGNAL_GROUPS: tuple[tuple[str, ...], ...] = (
    SYNC_LOAD_FIELDS,
    SYNC_SLEEP_FIELDS,
    SYNC_HEART_FIELDS,
    SYNC_ENERGY_FIELDS,
)

# At least 3 of 4 groups → likely a real watch sync, not a sparse manual doc.
MIN_WATCH_SYNC_SIGNAL_GROUPS: int = 3


def _has_usable_field(row: dict[str, Any], keys: tuple[str, ...]) -> bool:
    return any(not is_absent_or_weak(row.get(key)) for key in keys)


def count_watch_sync_signal_groups(row: dict[str, Any]) -> int:
    """How many watch-sync categories (load/sleep/heart/energy) have usable values."""
    return sum(1 for group in SYNC_SIGNAL_GROUPS if _has_usable_field(row, group))


def is_quality_history_day(row: dict[str, Any]) -> bool:
    """Day counts toward history confidence when it looks like a real wearable sync."""
    return count_watch_sync_signal_groups(row) >= MIN_WATCH_SYNC_SIGNAL_GROUPS


def count_quality_history_days(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows if is_quality_history_day(row))
