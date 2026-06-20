"""Shared Pydantic types and validators for API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

RiskLevel = Literal["Low", "Medium", "High"]

DATE_KEY_FORMAT = "%Y-%m-%d"


def validate_date_key(value: object) -> object:
    """Validate Firestore/API day keys (yyyy-MM-dd). Pass-through for None."""
    if value is None:
        return value
    if not isinstance(value, str):
        raise TypeError("date must be a string")
    normalized = value.strip()
    datetime.strptime(normalized, DATE_KEY_FORMAT)
    return normalized
