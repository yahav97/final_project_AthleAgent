"""Population-average nutrition inputs when a user has no logged meals.

Defaults align with medians in ``ML_model/athlete_injury_data.csv`` (synthetic training cohort).
"""

from __future__ import annotations

from typing import Any

from config import settings


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


def apply_nutrition_population_defaults(primary: dict[str, Any] | None) -> tuple[dict[str, Any], bool]:
    """
    Fill missing nutrition aggregates from population averages (no history scan).

    Returns ``(merged_doc, imputed)`` where ``imputed`` is True when any field was
    missing from ``primary`` (yesterday had no complete meal log).
    """
    defaults = nutrition_population_defaults()
    source = dict(primary or {})
    imputed = any(source.get(key) is None for key in NUTRITION_FIELD_KEYS)
    out = dict(source)
    for key in NUTRITION_FIELD_KEYS:
        if out.get(key) is None:
            out[key] = defaults[key]
    return out, imputed
