"""Population-average nutrition inputs when a user has no logged meals."""

from __future__ import annotations

from typing import Any

from services.model_features import DEFAULT_FEATURE_VALUES

# Aligned with model training defaults (~2500 kcal) and typical athlete macro split.
NUTRITION_POPULATION_DEFAULTS: dict[str, int | float] = {
    "totalProtein": 125,
    "totalCarbs": 290,
    "mealsLoggedCount": 3,
    "totalCalories": int(DEFAULT_FEATURE_VALUES["nutrition_intake_calories"]),
}

NUTRITION_FIELD_KEYS: tuple[str, ...] = tuple(NUTRITION_POPULATION_DEFAULTS.keys())


def apply_nutrition_population_defaults(primary: dict[str, Any] | None) -> tuple[dict[str, Any], bool]:
    """
    Fill missing nutrition aggregates from population averages (no history scan).

    Returns ``(merged_doc, imputed)`` where ``imputed`` is True when any field was
    missing from ``primary`` (yesterday had no complete meal log).
    """
    source = dict(primary or {})
    imputed = any(source.get(key) is None for key in NUTRITION_FIELD_KEYS)
    out = dict(source)
    for key in NUTRITION_FIELD_KEYS:
        if out.get(key) is None:
            out[key] = NUTRITION_POPULATION_DEFAULTS[key]
    return out, imputed
