"""Population-average nutrition inputs when a user has no logged meals.

Defaults align with medians in ``ML_model/athlete_injury_data.csv`` (synthetic training cohort).
"""

from __future__ import annotations

import math
from typing import Any

from config import settings
from schemas.inference import InjuryPredictionRequest

NutritionAggregateFieldNames = tuple[str, ...]

NUTRITION_AGGREGATE_FIELDS: NutritionAggregateFieldNames = (
    "totalProtein",
    "totalCarbs",
    "mealsLoggedCount",
    "totalCalories",
)


def nutrition_population_defaults() -> dict[str, int | float]:
    """Return imputation defaults (reads current settings on each call)."""
    return {
        "totalProtein": settings.NUTRITION_DEFAULT_PROTEIN,
        "totalCarbs": settings.NUTRITION_DEFAULT_CARBS,
        "mealsLoggedCount": settings.NUTRITION_DEFAULT_MEALS_LOGGED,
        "totalCalories": settings.NUTRITION_DEFAULT_CALORIES,
    }


def is_weak_nutrition_value(value: object) -> bool:
    """True when nutrition input is missing, null, zero, or non-finite."""
    if value is None:
        return True
    try:
        num = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return True
    return not math.isfinite(num) or num == 0.0


def apply_nutrition_population_defaults(
    nutrition_doc: dict[str, Any] | None,
) -> tuple[dict[str, Any], bool]:
    """
    Fill missing or zero nutrition aggregates from population averages (no history scan).

    Returns ``(merged_doc, imputed)`` where ``imputed`` is True when any field was
    weak in ``nutrition_doc`` (yesterday had no usable meal log).
    """
    defaults = nutrition_population_defaults()
    source = dict(nutrition_doc or {})
    imputed = any(
        is_weak_nutrition_value(source.get(field_name))
        for field_name in NUTRITION_AGGREGATE_FIELDS
    )
    out = dict(source)
    for field_name in NUTRITION_AGGREGATE_FIELDS:
        if is_weak_nutrition_value(out.get(field_name)):
            out[field_name] = defaults[field_name]
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

