"""Map InjuryPredictionRequest to a single model-ready DataFrame row."""

from __future__ import annotations

import math

import pandas as pd

from schemas.inference import InjuryPredictionRequest
from services.feature_engineering import compute_derived_features
from services.field_transforms import (
    daily_distance_km,
    hrv_proxy_from_resting_hr,
    injured_yesterday_as_feature,
    resting_hr as resolve_resting_hr,
)
from services.model_features import DEFAULT_FEATURE_VALUES, MODEL_FEATURE_COLUMNS
from services.preprocessing.helpers import safe_float
from services.preprocessing.scales import (
    energy_to_model_scale,
    soreness_to_model_scale,
    stress_to_model_scale,
)


def injury_request_to_model_dataframe(payload: InjuryPredictionRequest) -> pd.DataFrame:
    """
    Build one model-ready row: Android-shaped request → engineered → imputed DataFrame.

    Returns a DataFrame with exactly MODEL_FEATURE_COLUMNS (same order as training CSV).
    """
    payload_dict = payload.model_dump()
    injured_yesterday = float(
        max(0.0, min(1.0, injured_yesterday_as_feature(payload_dict.get("injuredYesterday"))))
    )

    sleep_minutes = payload_dict.get("sleepMinutes")
    sleep_hours = (
        float(sleep_minutes) / 60.0
        if sleep_minutes is not None
        else DEFAULT_FEATURE_VALUES["sleep_hours"]
    )
    if not math.isfinite(sleep_hours) or sleep_hours <= 0:
        sleep_hours = float(DEFAULT_FEATURE_VALUES["sleep_hours"])
    sleep_hours = float(max(3.0, min(12.0, sleep_hours)))

    steps = max(0.0, safe_float(payload_dict.get("steps"), 0.0))
    distance_m = max(0.0, safe_float(payload_dict.get("distanceMeters"), 0.0))
    daily_distance_km_val = float(min(60.0, daily_distance_km(distance_m, steps)))

    active_cal = max(0.0, safe_float(payload_dict.get("activeCalories"), 0.0))
    total_burned_health = max(0.0, safe_float(payload_dict.get("totalCalories"), 0.0))
    bmr = max(0.0, safe_float(payload_dict.get("bmrCalories"), 0.0))
    total_burned = float(
        total_burned_health
        if total_burned_health > 0
        else (
            bmr + active_cal
            if (bmr > 0 or active_cal > 0)
            else DEFAULT_FEATURE_VALUES["total_calories_burned"]
        )
    )
    if total_burned <= 0:
        total_burned = float(DEFAULT_FEATURE_VALUES["total_calories_burned"])
    total_burned = float(min(9000.0, total_burned))

    protein_g = max(0.0, safe_float(payload_dict.get("totalProtein"), 0.0))
    carbs_g = max(0.0, safe_float(payload_dict.get("totalCarbs"), 0.0))
    meals_logged = max(0.0, safe_float(payload_dict.get("mealsLoggedCount"), 0.0))
    intake_sum_logged = max(0.0, safe_float(payload_dict.get("nutritionTotalCalories"), 0.0))
    intake_sum_logged = float(min(8000.0, intake_sum_logged))
    macro_energy = protein_g * 4.0 + carbs_g * 4.0
    estimated_intake_from_macros = macro_energy * 1.2 if macro_energy > 0 else 0.0
    nutrition_intake_calories = (
        intake_sum_logged
        if intake_sum_logged > 0
        else (
            estimated_intake_from_macros
            if estimated_intake_from_macros > 0
            else float(DEFAULT_FEATURE_VALUES["nutrition_intake_calories"])
        )
    )
    if meals_logged > 0 and intake_sum_logged <= 0 and estimated_intake_from_macros <= 0:
        nutrition_intake_calories = float(
            DEFAULT_FEATURE_VALUES["nutrition_intake_calories"] * min(1.25, 0.6 + meals_logged * 0.2)
        )
    nutrition_intake_calories = float(min(7000.0, max(0.0, nutrition_intake_calories)))

    daily_calories = (
        estimated_intake_from_macros
        if estimated_intake_from_macros > 0
        else float(DEFAULT_FEATURE_VALUES["daily_calories"])
    )
    if intake_sum_logged > 0:
        daily_calories = float(max(800.0, min(7000.0, intake_sum_logged)))
    if meals_logged > 0 and macro_energy <= 0 and intake_sum_logged <= 0:
        daily_calories = float(
            DEFAULT_FEATURE_VALUES["daily_calories"] * min(1.25, 0.6 + meals_logged * 0.2)
        )
    daily_calories = float(min(7000.0, max(800.0, daily_calories)))

    workout_intensity = max(0.0, min(240.0, daily_distance_km_val * 5.5 + active_cal / 40.0))
    sensor_cadence = safe_float(payload_dict.get("avgCadence"), 0.0)
    if sensor_cadence > 0:
        avg_cadence = float(max(120.0, min(200.0, sensor_cadence)))
    elif steps > 0 and daily_distance_km_val > 0.05:
        est_minutes = max(10.0, workout_intensity)
        avg_cadence = float(max(120.0, min(200.0, steps / est_minutes)))
    else:
        avg_cadence = float(DEFAULT_FEATURE_VALUES["avg_cadence"])

    weight_kg = payload_dict.get("weightKg")
    height_cm = payload_dict.get("heightCm")
    height_m = 1.75
    if height_cm is not None and safe_float(height_cm, 0.0) > 100:
        height_m = float(height_cm) / 100.0
    bmi = DEFAULT_FEATURE_VALUES["bmi"]
    if weight_kg is not None and safe_float(weight_kg, 0.0) > 0:
        bmi = float(weight_kg) / (height_m**2)
    bmi = float(max(15.0, min(45.0, bmi)))

    age_val = float(DEFAULT_FEATURE_VALUES["age"])
    age_raw = payload_dict.get("age")
    if age_raw is not None:
        try:
            age_val = float(max(12.0, min(90.0, int(age_raw))))
        except (TypeError, ValueError):
            age_val = float(DEFAULT_FEATURE_VALUES["age"])

    history_injury_count = float(DEFAULT_FEATURE_VALUES["history_injury_count"])
    hist_raw = payload_dict.get("historyInjuryCount")
    if hist_raw is None:
        hist_raw = payload_dict.get("history_injury_count")
    if hist_raw is not None:
        try:
            history_injury_count = float(max(0.0, min(50.0, int(hist_raw))))
        except (TypeError, ValueError):
            history_injury_count = float(DEFAULT_FEATURE_VALUES["history_injury_count"])

    hr_avg = safe_float(payload_dict.get("heartRateAvg"), 0.0)
    resting_hr_val = resolve_resting_hr(
        safe_float(payload_dict.get("restingHeartRate"), 0.0),
        safe_float(payload_dict.get("heartRateMin"), 0.0),
        hr_avg,
        default=float(DEFAULT_FEATURE_VALUES["resting_hr"]),
    )

    hrv_rmssd = safe_float(payload_dict.get("hrvRmssd"), 0.0)
    if hrv_rmssd > 0:
        hrv_score = float(max(30.0, min(105.0, hrv_rmssd)))
    elif hr_avg > 0:
        hrv_score = hrv_proxy_from_resting_hr(resting_hr_val)
    else:
        hrv_score = float(DEFAULT_FEATURE_VALUES["hrv_score"])

    body_fat_pct = safe_float(payload_dict.get("bodyFatPct"), DEFAULT_FEATURE_VALUES["body_fat_pct"])
    body_fat_pct = float(max(3.0, min(50.0, body_fat_pct)))
    vo2_max = safe_float(payload_dict.get("vo2Max"), DEFAULT_FEATURE_VALUES["vo2_max"])
    vo2_max = float(max(15.0, min(90.0, vo2_max)))

    elevation_gained = safe_float(
        payload_dict.get("elevationGainedMeters"),
        DEFAULT_FEATURE_VALUES["elevation_gained_m"],
    )
    elevation_gained = float(max(0.0, min(5000.0, elevation_gained)))
    floors_climbed = safe_float(payload_dict.get("floorsClimbed"), DEFAULT_FEATURE_VALUES["floors_climbed"])
    floors_climbed = float(max(0.0, min(200.0, floors_climbed)))

    sensor_avg_speed = safe_float(payload_dict.get("avgSpeed"), 0.0)
    sensor_max_speed = safe_float(payload_dict.get("maxSpeed"), 0.0)
    if sensor_avg_speed > 0:
        avg_speed = float(max(0.0, min(30.0, sensor_avg_speed)))
    elif daily_distance_km_val > 0.05 and workout_intensity > 5:
        avg_speed = float(max(0.0, min(30.0, daily_distance_km_val / (workout_intensity / 60.0))))
    else:
        avg_speed = float(DEFAULT_FEATURE_VALUES["avg_speed"])
    max_speed = float(max(0.0, min(40.0, sensor_max_speed))) if sensor_max_speed > 0 else avg_speed * 1.3

    avg_power = safe_float(payload_dict.get("avgPower"), DEFAULT_FEATURE_VALUES["avg_power"])
    avg_power = float(max(0.0, min(800.0, avg_power)))

    respiratory_rate = safe_float(
        payload_dict.get("respiratoryRate"),
        DEFAULT_FEATURE_VALUES["respiratory_rate"],
    )
    respiratory_rate = float(max(6.0, min(40.0, respiratory_rate)))
    spo2 = safe_float(payload_dict.get("oxygenSaturation"), DEFAULT_FEATURE_VALUES["spo2"])
    spo2 = float(max(80.0, min(100.0, spo2)))

    partial: dict[str, float] = {
        "bmi": float(bmi),
        "age": age_val,
        "body_fat_pct": body_fat_pct,
        "vo2_max": vo2_max,
        "history_injury_count": history_injury_count,
        "injured_yesterday": injured_yesterday,
        "daily_distance_km": float(daily_distance_km_val),
        "workout_intensity_minutes": float(workout_intensity),
        "avg_cadence": float(avg_cadence),
        "elevation_gained_m": elevation_gained,
        "floors_climbed": floors_climbed,
        "avg_speed": avg_speed,
        "max_speed": max_speed,
        "avg_power": avg_power,
        "active_calories_burned": active_cal,
        "sleep_hours": float(sleep_hours),
        "hrv_score": float(hrv_score),
        "resting_hr": float(resting_hr_val),
        "respiratory_rate": respiratory_rate,
        "spo2": spo2,
        "nutrition_intake_calories": float(nutrition_intake_calories),
        "daily_calories": float(daily_calories),
        "total_calories_burned": float(total_burned),
        "stress_level": stress_to_model_scale(payload_dict.get("stressLevel")),
        "muscle_soreness": soreness_to_model_scale(payload_dict.get("muscleSoreness")),
        "energy_level": energy_to_model_scale(payload_dict.get("energyLevel")),
        "_active_calories": active_cal,
        "_bmr_calories": bmr,
    }

    derived = compute_derived_features(partial)
    partial.update(derived)
    partial.pop("_active_calories", None)
    partial.pop("_bmr_calories", None)

    partial["calorie_balance"] = float(partial["daily_calories"] - partial["total_calories_burned"])
    partial["acwr_ratio_ma7"] = float(partial["acwr_ratio"])
    partial["sleep_hours_ma7"] = float(partial["sleep_hours"])
    partial["load_recovery_imbalance"] = float(partial["acwr_ratio"] * partial["sleep_debt_3d"])
    partial["speed_intensity_ratio"] = float(
        min(5.0, partial["max_speed"] / (partial["avg_speed"] + 0.1))
    )

    out: dict[str, float] = {}
    for column in MODEL_FEATURE_COLUMNS:
        value = partial.get(column)
        if value is None or (isinstance(value, float) and not math.isfinite(value)):
            value = DEFAULT_FEATURE_VALUES[column]
        out[column] = float(value)

    frame = pd.DataFrame([out], columns=MODEL_FEATURE_COLUMNS)
    return frame.astype("float64").fillna(pd.Series(DEFAULT_FEATURE_VALUES))
