"""Merge Firestore docs into logical wake-up-day history rows."""

from __future__ import annotations

from typing import Any

# Sleep is written to the wake-up calendar day; physical load to the prior day.
SLEEP_MINUTES_FIELD_NAMES: tuple[str, ...] = ("sleepMinutes", "sleep_minutes")


def merge_wake_up_day_row(
    wake_up_key: str,
    physical_doc: dict[str, Any] | None,
    wake_doc: dict[str, Any] | None,
    checkin_doc: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """
    Build one logical wake-up day (same policy as ``firestore_mapping``).

    - Physical / wearable load: ``daily_health/{wake_up - 1 day}``
    - Sleep: ``daily_health/{wake_up}``
    - Survey: ``daily_checkins/{wake_up}``
    """
    physical = dict(physical_doc or {})
    wake = dict(wake_doc or {})
    checkin = dict(checkin_doc or {})
    if not physical and not wake and not checkin:
        return None

    row = dict(physical)
    for key in SLEEP_MINUTES_FIELD_NAMES:
        if key in wake:
            row[key] = wake[key]
    row.update(checkin)
    row["date_key"] = wake_up_key
    return row
