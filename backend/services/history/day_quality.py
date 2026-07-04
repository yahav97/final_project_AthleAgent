"""Per-day signal checks for history-window confidence."""

from __future__ import annotations

from typing import Any

from config import settings
from services.preprocessing.helpers import is_absent_or_weak

WatchSyncFieldNames = tuple[str, ...]

# Evaluated on merged wake-up-day rows (physical@W-1, sleep@W) from fetch_user_history.
LOAD_FIELD_NAMES: WatchSyncFieldNames = ("distanceMeters", "steps")
SLEEP_FIELD_NAMES: WatchSyncFieldNames = ("sleepMinutes",)
HEART_FIELD_NAMES: WatchSyncFieldNames = (
    "heartRateAvg",
    "restingHeartRate",
    "hrvRmssd",
)
ENERGY_FIELD_NAMES: WatchSyncFieldNames = (
    "activeCalories",
    "totalCalories",
    "bmrCalories",
)

WATCH_SYNC_SIGNAL_GROUPS: dict[str, WatchSyncFieldNames] = {
    "load": LOAD_FIELD_NAMES,
    "sleep": SLEEP_FIELD_NAMES,
    "heart": HEART_FIELD_NAMES,
    "energy": ENERGY_FIELD_NAMES,
}


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
    return count_watch_sync_signal_groups(row) >= settings.HISTORY_MIN_WATCH_SYNC_SIGNAL_GROUPS


def count_quality_history_days(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows if is_quality_history_day(row))
