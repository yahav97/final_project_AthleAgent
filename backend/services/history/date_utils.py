"""Firestore date key parsing."""

from __future__ import annotations

from datetime import datetime, timedelta


def to_date_key(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def date_keys_in_range(start_day: datetime, end_day: datetime) -> list[str]:
    keys: list[str] = []
    day = start_day
    while day <= end_day:
        keys.append(day.strftime("%Y-%m-%d"))
        day += timedelta(days=1)
    return keys
