"""Build model-side feature dict from an InjuryPredictionRequest payload."""

from __future__ import annotations

from typing import Any

from services.field_transforms import (
    daily_distance_km,
    parse_injured_yesterday_flag,
    resolve_model_age,
    resting_hr as resolve_resting_hr,
)
from services.model_features import DEFAULT_FEATURE_VALUES
from services.preprocessing.helpers import safe_float
from services.preprocessing.scales import (
    energy_to_model_scale,
    soreness_to_model_scale,
    stress_to_model_scale,
)

DEFAULT_BMI = float(DEFAULT_FEATURE_VALUES["bmi"])

ModelFeatureValues = dict[str, float]


def sleep_hours_from_minutes(sleep_minutes: object | None) -> float:
    if sleep_minutes is None:
        return 0.0
    return safe_float(sleep_minutes) / 60.0


def total_calories_burned(
    active_calories: float,
    health_total_calories: float,
    bmr_calories: float,
) -> float:
    if health_total_calories > 0:
        return health_total_calories
    if bmr_calories > 0 or active_calories > 0:
        return bmr_calories + active_calories
    return 0.0


def nutrition_calorie_estimates(
    protein_grams: float,
    carb_grams: float,
    logged_calories: float,
) -> tuple[float, float]:
    """Return (nutrition_intake_calories, daily_calories) from macros or logged sum."""
    macro_calories = protein_grams * 4.0 + carb_grams * 4.0
    if logged_calories > 0:
        return logged_calories, logged_calories
    if macro_calories > 0:
        return macro_calories * 1.2, macro_calories
    return 0.0, 0.0


def workout_intensity_minutes(daily_distance_km: float, active_calories: float) -> float:
    return daily_distance_km * 5.5 + active_calories / 40.0


def estimate_avg_cadence(
    sensor_cadence: float,
    steps: float,
    daily_distance_km: float,
    workout_minutes: float,
) -> float:
    if sensor_cadence > 0:
        return sensor_cadence
    if steps > 0 and daily_distance_km > 0:
        return steps / max(workout_minutes, 1.0)
    return 0.0


def estimate_speed_kmh(
    sensor_avg_speed: float,
    sensor_max_speed: float,
    daily_distance_km: float,
    workout_minutes: float,
) -> tuple[float, float]:
    if sensor_avg_speed > 0:
        avg_speed = sensor_avg_speed
    elif daily_distance_km > 0 and workout_minutes > 0:
        avg_speed = daily_distance_km / (workout_minutes / 60.0)
    else:
        avg_speed = 0.0
    max_speed = sensor_max_speed if sensor_max_speed > 0 else avg_speed * 1.3
    return float(avg_speed), float(max_speed)


def bmi_from_body_metrics(weight_kg: float, height_cm: float) -> float:
    if weight_kg > 0 and height_cm > 0:
        height_m = height_cm / 100.0
        return weight_kg / (height_m**2)
    return DEFAULT_BMI


def history_injury_count_from_payload(raw: object | None) -> float:
    if raw is None:
        return 0.0
    try:
        return float(int(raw))
    except (TypeError, ValueError):
        return 0.0


def base_model_features_from_request(payload_dict: dict[str, Any]) -> ModelFeatureValues:
    """Map API/Firestore request fields to model-side names (before derived features)."""
    injured_flag = parse_injured_yesterday_flag(payload_dict.get("injuredYesterday"))
    injured_yesterday = float(injured_flag if injured_flag is not None else 0)

    sleep_hours = sleep_hours_from_minutes(payload_dict.get("sleepMinutes"))

    steps = safe_float(payload_dict.get("steps"))
    distance_meters = safe_float(payload_dict.get("distanceMeters"))
    daily_distance_km_value = float(daily_distance_km(distance_meters, steps))

    active_calories = safe_float(payload_dict.get("activeCalories"))
    bmr_calories = safe_float(payload_dict.get("bmrCalories"))
    total_burned = total_calories_burned(
        active_calories,
        safe_float(payload_dict.get("totalCalories")),
        bmr_calories,
    )

    protein_grams = safe_float(payload_dict.get("totalProtein"))
    carb_grams = safe_float(payload_dict.get("totalCarbs"))
    logged_calories = safe_float(payload_dict.get("nutritionTotalCalories"))
    nutrition_intake_calories, daily_calories = nutrition_calorie_estimates(
        protein_grams,
        carb_grams,
        logged_calories,
    )

    workout_minutes = workout_intensity_minutes(daily_distance_km_value, active_calories)
    avg_cadence = estimate_avg_cadence(
        safe_float(payload_dict.get("avgCadence")),
        steps,
        daily_distance_km_value,
        workout_minutes,
    )
    avg_speed, max_speed = estimate_speed_kmh(
        safe_float(payload_dict.get("avgSpeed")),
        safe_float(payload_dict.get("maxSpeed")),
        daily_distance_km_value,
        workout_minutes,
    )

    heart_rate_avg = safe_float(payload_dict.get("heartRateAvg"))
    resting_hr_value = resolve_resting_hr(
        safe_float(payload_dict.get("restingHeartRate")),
        safe_float(payload_dict.get("heartRateMin")),
        heart_rate_avg,
        default=0.0,
    )

    hrv_rmssd = safe_float(payload_dict.get("hrvRmssd"))
    hrv_score = hrv_rmssd if hrv_rmssd > 0 else 0.0

    return {
        "bmi": float(bmi_from_body_metrics(
            safe_float(payload_dict.get("weightKg")),
            safe_float(payload_dict.get("heightCm")),
        )),
        "age": resolve_model_age(payload_dict.get("age")),
        "body_fat_pct": safe_float(payload_dict.get("bodyFatPct")),
        "vo2_max": safe_float(payload_dict.get("vo2Max")),
        "history_injury_count": history_injury_count_from_payload(
            payload_dict.get("historyInjuryCount")
        ),
        "injured_yesterday": injured_yesterday,
        "daily_distance_km": daily_distance_km_value,
        "workout_intensity_minutes": float(workout_minutes),
        "avg_cadence": float(avg_cadence),
        "elevation_gained_m": safe_float(payload_dict.get("elevationGainedMeters")),
        "floors_climbed": safe_float(payload_dict.get("floorsClimbed")),
        "avg_speed": avg_speed,
        "max_speed": max_speed,
        "avg_power": safe_float(payload_dict.get("avgPower")),
        "active_calories_burned": active_calories,
        "bmr_calories": bmr_calories,
        "sleep_hours": float(sleep_hours),
        "hrv_score": float(hrv_score),
        "resting_hr": float(resting_hr_value),
        "respiratory_rate": safe_float(payload_dict.get("respiratoryRate")),
        "spo2": safe_float(payload_dict.get("oxygenSaturation")),
        "nutrition_intake_calories": float(nutrition_intake_calories),
        "daily_calories": float(daily_calories),
        "total_calories_burned": float(total_burned),
        "stress_level": stress_to_model_scale(payload_dict.get("stressLevel")),
        "muscle_soreness": soreness_to_model_scale(payload_dict.get("muscleSoreness")),
        "energy_level": energy_to_model_scale(payload_dict.get("energyLevel")),
    }


def add_same_day_composite_features(features: ModelFeatureValues) -> ModelFeatureValues:
    """Fill same-day proxy columns that training computes from multi-day history."""
    out = dict(features)
    out["calorie_balance"] = float(out["daily_calories"] - out["total_calories_burned"])
    out["acwr_ratio_ma7"] = float(out["acwr_ratio"])
    out["sleep_hours_ma7"] = float(out["sleep_hours"])
    out["load_recovery_imbalance"] = float(out["acwr_ratio"] * out["sleep_debt_3d"])
    out["speed_intensity_ratio"] = float(
        out["max_speed"] / (out["avg_speed"] + 0.1) if out["avg_speed"] > 0 else 0.0
    )
    return out
