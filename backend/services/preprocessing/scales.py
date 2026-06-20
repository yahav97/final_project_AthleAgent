"""Map Android UI scales to model training scales."""

from __future__ import annotations

from services.model_features import DEFAULT_FEATURE_VALUES


def stress_to_model_scale(value: int | None) -> float:
    """Map Android stress (often 0–100) to training scale 1–10."""
    if value is None:
        return float(DEFAULT_FEATURE_VALUES["stress_level"])
    scaled = float(value)
    if scaled > 10.0:
        scaled = max(1.0, min(10.0, round(scaled / 10.0)))
    return float(max(1.0, min(10.0, scaled)))


def soreness_to_model_scale(value: int | None) -> float:
    """Map typical 1–5 UI soreness to training 1–10."""
    if value is None:
        return float(DEFAULT_FEATURE_VALUES["muscle_soreness"])
    scaled = float(value)
    if scaled <= 5.0:
        scaled = max(1.0, min(10.0, scaled * 2.0 - 0.5))
    return float(max(1.0, min(10.0, scaled)))


def energy_to_model_scale(value: int | None) -> float:
    """Map Android energy (often 0–100) to training scale 1–10."""
    if value is None:
        return float(DEFAULT_FEATURE_VALUES["energy_level"])
    scaled = float(value)
    if scaled > 10.0:
        scaled = max(1.0, min(10.0, round(scaled / 10.0)))
    return float(max(1.0, min(10.0, scaled)))
