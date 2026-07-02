"""Unit tests for request → model feature mapping helpers."""

from __future__ import annotations

import pytest

from services.preprocessing.request_features import (
    base_model_features_from_request,
    bmi_from_body_metrics,
    nutrition_calorie_estimates,
    total_calories_burned,
    workout_intensity_minutes,
)

pytestmark = pytest.mark.unit


class TestNutritionCalorieEstimates:
    def test_prefers_logged_calories(self):
        intake, daily = nutrition_calorie_estimates(100, 200, 2400)
        assert intake == 2400
        assert daily == 2400

    def test_estimates_from_macros_when_logged_missing(self):
        intake, daily = nutrition_calorie_estimates(130, 300, 0)
        assert daily == pytest.approx(1720.0)
        assert intake == pytest.approx(2064.0)


class TestTotalCaloriesBurned:
    def test_prefers_health_total(self):
        assert total_calories_burned(400, 2500, 1800) == 2500

    def test_sums_bmr_and_active_when_health_total_missing(self):
        assert total_calories_burned(400, 0, 1800) == 2200


class TestBaseModelFeatures:
    def test_maps_core_load_and_sleep_fields(self):
        features = base_model_features_from_request(
            {
                "age": 28,
                "sleepMinutes": 420,
                "steps": 8000,
                "distanceMeters": 6000,
                "activeCalories": 500,
                "stressLevel": 40,
                "muscleSoreness": 3,
                "energyLevel": 70,
            }
        )
        assert features["sleep_hours"] == pytest.approx(7.0)
        assert features["daily_distance_km"] == pytest.approx(6.0)
        assert features["active_calories_burned"] == 500
        assert features["workout_intensity_minutes"] == pytest.approx(
            workout_intensity_minutes(6.0, 500)
        )

    def test_bmi_uses_default_when_body_metrics_missing(self):
        features = base_model_features_from_request({"age": 28})
        assert features["bmi"] == pytest.approx(bmi_from_body_metrics(0, 0))
