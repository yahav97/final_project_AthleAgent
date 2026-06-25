"""Small numeric helpers for preprocessing."""

from __future__ import annotations

import math
from typing import Any, Mapping


def safe_float(value: object, fallback: float = 0.0) -> float:
    """Convert arbitrary numeric-like value to finite float."""
    try:
        out = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float(fallback)
    if not math.isfinite(out):
        return float(fallback)
    return out


def is_present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, str):
        return bool(value.strip())
    return True


def positive_numeric(value: object) -> float:
    """Return a finite numeric value only when strictly greater than zero."""
    try:
        out = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(out) or out <= 0:
        return 0.0
    return out


def has_positive_load_signal(payload: Mapping[str, Any]) -> bool:
    """True when prior-day load has a meaningful non-zero signal."""
    return (
        positive_numeric(payload.get("steps")) > 0
        or positive_numeric(payload.get("distanceMeters")) > 0
        or positive_numeric(payload.get("activeCalories")) > 0
    )
