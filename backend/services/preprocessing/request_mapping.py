"""Map InjuryPredictionRequest to a single model-ready DataFrame row."""

from __future__ import annotations

import math
from typing import Any, cast

import pandas as pd

from schemas.inference import InjuryPredictionRequest
from services.feature_engineering import compute_derived_features
from services.field_transforms import (
    daily_distance_km,
    parse_injured_yesterday_flag,
    resolve_model_age,
    resting_hr as resolve_resting_hr,
)
from services.model_features import DEFAULT_FEATURE_VALUES, MODEL_FEATURE_COLUMNS
from services.preprocessing.helpers import safe_float

DEFAULT_BMI = float(DEFAULT_FEATURE_VALUES["bmi"])
from services.preprocessing.scales import (
    energy_to_model_scale,
    soreness_to_model_scale,
    stress_to_model_scale,
)


def injury_request_to_model_dataframe(payload: InjuryPredictionRequest) -> pd.DataFrame:
    """
    Build one model-ready row: Android-shaped request → engineered DataFrame.

    Policy:
    - Trust frontend payloads; no range clamping on received values.
    - Missing / NaN numeric inputs become 0.0 (confidence handled separately).
    - Survey fields use fixed scale mapping (see ``scales``).
    - Historical rolling features are enriched later in ``confidence`` module.
    """
    payload_dict = payload.model_dump()

    injured_flag = parse_injured_yesterday_flag(payload_dict.get("injuredYesterday"))
    injured_yesterday = float(injured_flag if injured_flag is not None else 0)

    sleep_minutes = payload_dict.get("sleepMinutes")
    sleep_hours = safe_float(sleep_minutes) / 60.0 if sleep_minutes is not None else 0.0

    steps = safe_float(payload_dict.get("steps"))
    distance_m = safe_float(payload_dict.get("distanceMeters"))
    daily_distance_km_val = float(daily_distance_km(distance_m, steps))

    active_cal = safe_float(payload_dict.get("activeCalories"))
    total_burned_health = safe_float(payload_dict.get("totalCalories"))
    bmr = safe_float(payload_dict.get("bmrCalories"))
    total_burned = (
        total_burned_health
        if total_burned_health > 0
        else (bmr + active_cal if (bmr > 0 or active_cal > 0) else 0.0)
    )

    protein_g = safe_float(payload_dict.get("totalProtein"))
    carbs_g = safe_float(payload_dict.get("totalCarbs"))
    intake_sum_logged = safe_float(payload_dict.get("nutritionTotalCalories"))
    macro_energy = protein_g * 4.0 + carbs_g * 4.0
    nutrition_intake_calories = (
        intake_sum_logged if intake_sum_logged > 0 else (macro_energy * 1.2 if macro_energy > 0 else 0.0)
    )
    daily_calories = intake_sum_logged if intake_sum_logged > 0 else (macro_energy if macro_energy > 0 else 0.0)

    workout_intensity = daily_distance_km_val * 5.5 + active_cal / 40.0

    sensor_cadence = safe_float(payload_dict.get("avgCadence"))
    if sensor_cadence > 0:
        avg_cadence = sensor_cadence
    elif steps > 0 and daily_distance_km_val > 0:
        est_minutes = max(workout_intensity, 1.0)
        avg_cadence = steps / est_minutes
    else:
        avg_cadence = 0.0

    weight_kg = safe_float(payload_dict.get("weightKg"))
    height_cm = safe_float(payload_dict.get("heightCm"))
    if weight_kg > 0 and height_cm > 0:
        height_m = height_cm / 100.0
        bmi = weight_kg / (height_m**2)
    else:
        bmi = DEFAULT_BMI

    age_val = resolve_model_age(payload_dict.get("age"))

    history_injury_count = 0.0
    hist_raw = payload_dict.get("historyInjuryCount")
    if hist_raw is not None:
        try:
            history_injury_count = float(int(hist_raw))
        except (TypeError, ValueError):
            history_injury_count = 0.0

    hr_avg = safe_float(payload_dict.get("heartRateAvg"))
    resting_hr_val = resolve_resting_hr(
        safe_float(payload_dict.get("restingHeartRate")),
        safe_float(payload_dict.get("heartRateMin")),
        hr_avg,
        default=0.0,
    )

    hrv_rmssd = safe_float(payload_dict.get("hrvRmssd"))
    hrv_score = hrv_rmssd if hrv_rmssd > 0 else 0.0

    body_fat_pct = safe_float(payload_dict.get("bodyFatPct"))
    vo2_max = safe_float(payload_dict.get("vo2Max"))
    elevation_gained = safe_float(payload_dict.get("elevationGainedMeters"))
    floors_climbed = safe_float(payload_dict.get("floorsClimbed"))

    sensor_avg_speed = safe_float(payload_dict.get("avgSpeed"))
    sensor_max_speed = safe_float(payload_dict.get("maxSpeed"))
    if sensor_avg_speed > 0:
        avg_speed = sensor_avg_speed
    elif daily_distance_km_val > 0 and workout_intensity > 0:
        avg_speed = daily_distance_km_val / (workout_intensity / 60.0)
    else:
        avg_speed = 0.0
    max_speed = sensor_max_speed if sensor_max_speed > 0 else avg_speed * 1.3

    avg_power = safe_float(payload_dict.get("avgPower"))
    respiratory_rate = safe_float(payload_dict.get("respiratoryRate"))
    spo2 = safe_float(payload_dict.get("oxygenSaturation"))

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
        "avg_speed": float(avg_speed),
        "max_speed": float(max_speed),
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
        partial["max_speed"] / (partial["avg_speed"] + 0.1) if partial["avg_speed"] > 0 else 0.0
    )

    out: dict[str, float] = {}
    for column in MODEL_FEATURE_COLUMNS:
        value = partial.get(column)
        if value is None or (isinstance(value, float) and not math.isfinite(value)):
            value = 0.0
        out[column] = float(value)

    feature_columns = list(MODEL_FEATURE_COLUMNS)
    frame = pd.DataFrame([out], columns=cast(Any, feature_columns))
    return frame.astype("float64").fillna(0.0)
