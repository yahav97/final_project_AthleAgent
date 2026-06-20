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


def is_present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, str):
        return bool(value.strip())
    return True
