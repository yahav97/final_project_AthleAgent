"""Map Android UI scales to model training scales."""

from __future__ import annotations

from services.preprocessing.helpers import safe_float


def _clamp_to_model_scale_1_10(value: float) -> float:
    return float(round(max(1.0, min(10.0, value))))


def _scale_large_ui_value_to_1_10(value: int | None) -> float:
    """Map Android 0–100 style inputs to training scale 1–10 (whole number)."""
    scaled = safe_float(value, fallback=0.0)
    if scaled > 10.0:
        scaled = max(1.0, min(10.0, round(scaled / 10.0)))
    return _clamp_to_model_scale_1_10(scaled)


def stress_to_model_scale(value: int | None) -> float:
    """Map Android stress (often 0–100) to training scale 1–10 (whole number)."""
    return _scale_large_ui_value_to_1_10(value)


def soreness_to_model_scale(value: int | None) -> float:
    """Map typical 1–5 UI soreness to training 1–10 (whole number)."""
    scaled = safe_float(value, fallback=0.0)
    if scaled <= 5.0:
        scaled = max(1.0, min(10.0, scaled * 2.0 - 0.5))
    return _clamp_to_model_scale_1_10(scaled)


def energy_to_model_scale(value: int | None) -> float:
    """Map Android energy (often 0–100) to training scale 1–10 (whole number)."""
    return _scale_large_ui_value_to_1_10(value)
