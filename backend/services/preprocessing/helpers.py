"""Small numeric helpers for preprocessing."""

from __future__ import annotations

import math


def safe_float(value: object, fallback: float = 0.0) -> float:
    """Convert arbitrary numeric-like value to finite float."""
    try:
        out = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float(fallback)
    if not math.isfinite(out):
        return float(fallback)
    return out


def is_explicit_zero_or_nan(value: object) -> bool:
    """True only when the client sent a value that is 0 or non-finite."""
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    try:
        num = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return True
    return math.isnan(num) or num == 0.0


def is_absent_or_weak(value: object) -> bool:
    """True when a required measurement is missing, null, empty, zero, or non-finite."""
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return is_explicit_zero_or_nan(value)
