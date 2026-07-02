"""Population-average nutrition inputs when a user has no logged meals.

Defaults align with medians in ``ML_model/athlete_injury_data.csv`` (synthetic training cohort).
"""

from __future__ import annotations

import math
from typing import Any

from config import settings
from schemas.inference import InjuryPredictionRequest


def nutrition_population_defaults() -> dict[str, int | float]:
    """Return imputation defaults (reads current settings on each call)."""
    return {
        "totalProtein": settings.NUTRITION_DEFAULT_PROTEIN,
        "totalCarbs": settings.NUTRITION_DEFAULT_CARBS,
        "mealsLoggedCount": settings.NUTRITION_DEFAULT_MEALS_LOGGED,
        "totalCalories": settings.NUTRITION_DEFAULT_CALORIES,
    }


NUTRITION_FIELD_KEYS: tuple[str, ...] = (
    "totalProtein",
    "totalCarbs",
    "mealsLoggedCount",
    "totalCalories",
)


def is_weak_nutrition_value(value: object) -> bool:
    """True when nutrition input is missing, null, zero, or non-finite."""
    if value is None:
        return True
    try:
        num = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return True
    return not math.isfinite(num) or num == 0.0


def apply_nutrition_population_defaults(primary: dict[str, Any] | None) -> tuple[dict[str, Any], bool]:
    """
    Fill missing or zero nutrition aggregates from population averages (no history scan).

    Returns ``(merged_doc, imputed)`` where ``imputed`` is True when any field was
    weak in ``primary`` (yesterday had no usable meal log).
    """
    defaults = nutrition_population_defaults()
    source = dict(primary or {})
    imputed = any(is_weak_nutrition_value(source.get(key)) for key in NUTRITION_FIELD_KEYS)
    out = dict(source)
    for key in NUTRITION_FIELD_KEYS:
        if is_weak_nutrition_value(out.get(key)):
            out[key] = defaults[key]
    return out, imputed


def resolve_request_nutrition(payload: InjuryPredictionRequest) -> InjuryPredictionRequest:
    """Apply population nutrition defaults on the inference request when values are weak."""
    nutrition, imputed = apply_nutrition_population_defaults(
        {
            "totalProtein": payload.totalProtein,
            "totalCarbs": payload.totalCarbs,
            "mealsLoggedCount": payload.mealsLoggedCount,
            "totalCalories": payload.nutritionTotalCalories,
        }
    )
    return payload.model_copy(
        update={
            "totalProtein": int(nutrition["totalProtein"]),
            "totalCarbs": int(nutrition["totalCarbs"]),
            "mealsLoggedCount": int(nutrition["mealsLoggedCount"]),
            "nutritionTotalCalories": float(nutrition["totalCalories"]),
            "nutritionImputed": bool(imputed or payload.nutritionImputed),
        }
    )
