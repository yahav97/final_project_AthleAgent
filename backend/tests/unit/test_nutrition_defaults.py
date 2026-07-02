"""Unit tests for population nutrition imputation."""

from __future__ import annotations

import pytest

from services.nutrition_defaults import apply_nutrition_population_defaults

pytestmark = pytest.mark.unit


class TestNutritionDefaults:
    def test_empty_primary_gets_population_defaults_and_imputed_flag(self):
        out, imputed = apply_nutrition_population_defaults({})
        assert imputed is True
        assert out["totalProtein"] == 130
        assert out["totalCarbs"] == 300
        assert out["mealsLoggedCount"] == 3
        assert out["totalCalories"] == 2600

    def test_yesterday_values_preserved_when_present(self):
        primary = {"totalProtein": 140, "totalCarbs": 310, "mealsLoggedCount": 4, "totalCalories": 2700}
        out, imputed = apply_nutrition_population_defaults(primary)
        assert imputed is False
        assert out == primary

    def test_partial_yesterday_sets_imputed_flag(self):
        primary = {"totalProtein": 150, "totalCalories": 2600}
        out, imputed = apply_nutrition_population_defaults(primary)
        assert imputed is True
        assert out["totalProtein"] == 150
        assert out["totalCalories"] == 2600
        assert out["totalCarbs"] == 300
        assert out["mealsLoggedCount"] == 3

    def test_zero_nutrition_values_get_population_defaults(self):
        primary = {
            "totalProtein": 0,
            "totalCarbs": 0,
            "mealsLoggedCount": 0,
            "totalCalories": 0,
        }
        out, imputed = apply_nutrition_population_defaults(primary)
        assert imputed is True
        assert out["totalProtein"] == 130
        assert out["totalCarbs"] == 300
        assert out["mealsLoggedCount"] == 3
        assert out["totalCalories"] == 2600
