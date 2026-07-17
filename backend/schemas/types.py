"""Shared Pydantic types and validators for API schemas."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Literal

RiskLevel = Literal["Low", "Medium", "High"]

DATE_KEY_FORMAT = "%Y-%m-%d"
MAX_DATE_FUTURE_DAYS = 1
MAX_DATE_PAST_DAYS = 730


def validate_date_key(value: object) -> object:
    """Validate Firestore/API day keys (yyyy-MM-dd). Pass-through for None."""
    if value is None:
        return value
    if not isinstance(value, str):
        raise TypeError("date must be a string")
    normalized = value.strip()
    parsed = datetime.strptime(normalized, DATE_KEY_FORMAT).date()
    today = date.today()
    if parsed > today + timedelta(days=MAX_DATE_FUTURE_DAYS):
        raise ValueError("date must not be in the future")
    if parsed < today - timedelta(days=MAX_DATE_PAST_DAYS):
        raise ValueError("date is too far in the past")
    return normalized
