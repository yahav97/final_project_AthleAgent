"""
Map InjuryPredictionRequest → single-row pandas DataFrame for sklearn.

Fills missing values (NaN-safe) and enforces column order for injury_model.pkl.
"""

from __future__ import annotations

import math

import pandas as pd

from schemas.inference import InjuryPredictionRequest
from services.feature_engineering import compute_derived_features
from services.model_features import DEFAULT_FEATURE_VALUES, MODEL_FEATURE_COLUMNS


def _stress_to_model_scale(value: int | None) -> float:
    """Map Android stress (often 0–100) to training scale 1–10."""
    if value is None:
        return float(DEFAULT_FEATURE_VALUES["stress_level"])
    v = float(value)
    if v > 10.0:
        v = max(1.0, min(10.0, round(v / 10.0)))
    return float(max(1.0, min(10.0, v)))


def _soreness_to_model_scale(value: int | None) -> float:
    """Map typical 1–5 UI soreness to training 1–10."""
    if value is None:
        return float(DEFAULT_FEATURE_VALUES["muscle_soreness"])
    v = float(value)
    if v <= 5.0:
        v = max(1.0, min(10.0, v * 2.0 - 0.5))
    return float(max(1.0, min(10.0, v)))


def injury_request_to_model_dataframe(payload: InjuryPredictionRequest) -> pd.DataFrame:
    """
    Build one model-ready row: Android-shaped request → engineered → imputed DataFrame.

    Returns a DataFrame with exactly MODEL_FEATURE_COLUMNS (same order as training CSV).
    """
    d = payload.model_dump()

    sleep_minutes = d.get("sleepMinutes")
    sleep_hours = (
        float(sleep_minutes) / 60.0 if sleep_minutes is not None else DEFAULT_FEATURE_VALUES["sleep_hours"]
    )
    if not math.isfinite(sleep_hours) or sleep_hours <= 0:
        sleep_hours = float(DEFAULT_FEATURE_VALUES["sleep_hours"])
    sleep_hours = float(max(3.0, min(12.0, sleep_hours)))

    steps = float(d.get("steps") or 0.0)
    distance_m = float(d.get("distanceMeters") or 0.0)
    daily_distance_km = distance_m / 1000.0 if distance_m > 0 else max(0.0, steps * 0.0008)

    active_cal = float(d.get("activeCalories") or 0.0)
    intake = d.get("totalCalories")
    burned = d.get("totalCalories")  # Android stores total under daily_health; use as both if needed
    daily_calories = float(intake if intake is not None else DEFAULT_FEATURE_VALUES["daily_calories"])
    bmr = float(d.get("bmrCalories") or 0.0)
    total_burned = float(
        (d.get("totalCalories") or 0) + active_cal * 0.25 + bmr * 0.15
        if (d.get("totalCalories") is not None or active_cal or bmr)
        else DEFAULT_FEATURE_VALUES["total_calories_burned"]
    )
    if total_burned <= 0:
        total_burned = float(DEFAULT_FEATURE_VALUES["total_calories_burned"])

    workout_intensity = max(0.0, min(240.0, daily_distance_km * 5.5 + active_cal / 40.0))
    avg_cadence = float(DEFAULT_FEATURE_VALUES["avg_cadence"])
    if steps > 0 and daily_distance_km > 0.05:
        est_minutes = max(10.0, workout_intensity)
        avg_cadence = float(max(120.0, min(200.0, steps / est_minutes)))

    weight_kg = d.get("weightKg")
    bmi = DEFAULT_FEATURE_VALUES["bmi"]
    if weight_kg is not None and float(weight_kg) > 0:
        height_m = 1.75
        bmi = float(weight_kg) / (height_m**2)

    hr_avg = d.get("heartRateAvg")
    resting_hr = float(hr_avg if hr_avg is not None else DEFAULT_FEATURE_VALUES["resting_hr"])
    resting_hr = float(max(38.0, min(95.0, resting_hr)))

    hrv_score = float(DEFAULT_FEATURE_VALUES["hrv_score"])
    if hr_avg is not None:
        hrv_score = float(max(30.0, min(100.0, 110.0 - resting_hr * 0.65)))

    partial: dict = {
        "age": float(DEFAULT_FEATURE_VALUES["age"]),
        "bmi": float(bmi),
        "history_injury_count": float(DEFAULT_FEATURE_VALUES["history_injury_count"]),
        "vo2_max": float(DEFAULT_FEATURE_VALUES["vo2_max"]),
        "daily_distance_km": float(daily_distance_km),
        "workout_intensity_minutes": float(workout_intensity),
        "avg_cadence": float(avg_cadence),
        "sleep_hours": float(sleep_hours),
        "hrv_score": float(hrv_score),
        "resting_hr": float(resting_hr),
        "daily_calories": float(daily_calories),
        "total_calories_burned": float(total_burned),
        "stress_level": _stress_to_model_scale(d.get("stressLevel")),
        "muscle_soreness": _soreness_to_model_scale(d.get("muscleSoreness")),
        "_active_calories": active_cal,
    }

    derived = compute_derived_features(partial)
    partial.update(derived)
    partial.pop("_active_calories", None)

    partial["calorie_balance"] = float(partial["daily_calories"] - partial["total_calories_burned"])

    out: dict[str, float] = {}
    for col in MODEL_FEATURE_COLUMNS:
        val = partial.get(col)
        if val is None or (isinstance(val, float) and not math.isfinite(val)):
            val = DEFAULT_FEATURE_VALUES[col]
        out[col] = float(val)

    frame = pd.DataFrame([out], columns=MODEL_FEATURE_COLUMNS)
    return frame.astype("float64").fillna(pd.Series(DEFAULT_FEATURE_VALUES))
