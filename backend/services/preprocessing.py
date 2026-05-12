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

TOLERANT_FIELDS: tuple[str, ...] = (
    "totalProtein",
    "totalCarbs",
    "mealsLoggedCount",
    "nutritionTotalCalories",
    "energyLevel",
    "heartRateMax",
    "heartRateMin",
    "activeCalories",
    "bodyFatPct",
    "vo2Max",
    "elevationGainedMeters",
    "floorsClimbed",
    "avgSpeed",
    "maxSpeed",
    "avgPower",
    "avgCadence",
    "respiratoryRate",
    "oxygenSaturation",
    "heightCm",
)

SENSITIVE_FIELDS: tuple[str, ...] = (
    "sleepMinutes",
    "steps",
    "distanceMeters",
    "heartRateAvg",
    "stressLevel",
    "muscleSoreness",
    "hrvRmssd",
    "restingHeartRate",
)

HARD_FIELDS: tuple[str, ...] = ("userId", "date")


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


def _energy_to_model_scale(value: int | None) -> float:
    """Map Android energy (often 0–100) to training scale 1–10 (same rule as stress)."""
    if value is None:
        return float(DEFAULT_FEATURE_VALUES["energy_level"])
    v = float(value)
    if v > 10.0:
        v = max(1.0, min(10.0, round(v / 10.0)))
    return float(max(1.0, min(10.0, v)))


def _injured_yesterday_float(raw: object) -> float:
    """Firestore ``injuredYesterday`` on today's doc → 0/1 feature."""
    if raw is None:
        return float(DEFAULT_FEATURE_VALUES["injured_yesterday"])
    if raw is True:
        return 1.0
    if raw is False:
        return 0.0
    try:
        return 1.0 if int(raw) else 0.0
    except (TypeError, ValueError):
        return float(DEFAULT_FEATURE_VALUES["injured_yesterday"])


def _safe_float(value: object, fallback: float = 0.0) -> float:
    """Convert arbitrary numeric-like value to finite float."""
    try:
        out = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float(fallback)
    if not math.isfinite(out):
        return float(fallback)
    return out


def _is_present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, str):
        return bool(value.strip())
    return True


def calculate_data_quality_score(payload: InjuryPredictionRequest) -> dict[str, object]:
    """
    Score current-day payload completeness and report hard-missing conditions.

    Score range: 0.0 - 1.0
    - tolerant missing fields do not reduce score
    - sensitive missing fields reduce score
    - hard requirements trigger red flag
    """
    d = payload.model_dump()
    hard_missing = [f for f in HARD_FIELDS if not _is_present(d.get(f))]
    sensitive_missing = [f for f in SENSITIVE_FIELDS if not _is_present(d.get(f))]

    has_load_signal = _is_present(d.get("steps")) or _is_present(d.get("distanceMeters"))
    has_recovery_signal = _is_present(d.get("sleepMinutes")) or (
        _is_present(d.get("stressLevel")) and _is_present(d.get("muscleSoreness"))
    )
    if not has_load_signal:
        hard_missing.append("load_signal")
    if not has_recovery_signal:
        hard_missing.append("recovery_signal")

    sensitive_penalty = 0.12 * len(sensitive_missing)
    score = max(0.0, min(1.0, 1.0 - sensitive_penalty))
    if hard_missing:
        score = min(score, 0.25)

    return {
        "score": float(score),
        "hard_missing": hard_missing,
        "sensitive_missing": sensitive_missing,
        "has_hard_blocker": bool(hard_missing),
    }


def validate_feature_vector_for_model(df: pd.DataFrame, model: object | None) -> pd.DataFrame:
    """
    Validate final model input against training contract.

    Ensures:
    - expected columns exist and are ordered exactly like training
    - all values are finite float64
    - critical scaled ranges remain in sane model bounds
    """
    expected_columns = None
    if isinstance(model, dict):
        cols = model.get("feature_columns")
        if isinstance(cols, list) and cols:
            expected_columns = [str(c) for c in cols]
        model = model.get("estimator")
    if expected_columns is None:
        feature_names = getattr(model, "feature_names_in_", None)
        if feature_names is not None:
            expected_columns = [str(c) for c in feature_names]
    if expected_columns:
        missing = [c for c in expected_columns if c not in df.columns]
        if missing:
            raise ValueError(f"Model expects missing feature columns: {missing}")
        df = df.loc[:, expected_columns]

    aligned = df.astype("float64")
    if not pd.Series(pd.notna(aligned.to_numpy().ravel())).all():
        raise ValueError("Feature vector contains NaN values")
    if not pd.Series(pd.Series(aligned.to_numpy().ravel()).map(math.isfinite)).all():
        raise ValueError("Feature vector contains non-finite values")

    if "stress_level" in aligned.columns:
        v = float(aligned["stress_level"].iloc[0])
        if v < 1.0 or v > 10.0:
            raise ValueError(f"stress_level out of expected scaled range [1,10]: {v}")
    if "muscle_soreness" in aligned.columns:
        v = float(aligned["muscle_soreness"].iloc[0])
        if v < 1.0 or v > 10.0:
            raise ValueError(f"muscle_soreness out of expected scaled range [1,10]: {v}")
    if "energy_level" in aligned.columns:
        v = float(aligned["energy_level"].iloc[0])
        if v < 1.0 or v > 10.0:
            raise ValueError(f"energy_level out of expected scaled range [1,10]: {v}")
    if "injured_yesterday" in aligned.columns:
        v = float(aligned["injured_yesterday"].iloc[0])
        if v < 0.0 or v > 1.0:
            raise ValueError(f"injured_yesterday out of expected range [0,1]: {v}")
    if "age" in aligned.columns:
        v = float(aligned["age"].iloc[0])
        if v < 12.0 or v > 90.0:
            raise ValueError(f"age out of expected range [12,90]: {v}")
    if "history_injury_count" in aligned.columns:
        v = float(aligned["history_injury_count"].iloc[0])
        if v < 0.0 or v > 50.0:
            raise ValueError(f"history_injury_count out of expected range [0,50]: {v}")
    if "nutrition_intake_calories" in aligned.columns:
        v = float(aligned["nutrition_intake_calories"].iloc[0])
        if v < 0.0 or v > 8000.0:
            raise ValueError(f"nutrition_intake_calories out of expected range [0,8000]: {v}")
    if "acwr_ratio" in aligned.columns:
        v = float(aligned["acwr_ratio"].iloc[0])
        if v < 0.35 or v > 2.8:
            raise ValueError(f"acwr_ratio out of expected range [0.35,2.8]: {v}")
    return aligned


def injury_request_to_model_dataframe(payload: InjuryPredictionRequest) -> pd.DataFrame:
    """
    Build one model-ready row: Android-shaped request → engineered → imputed DataFrame.

    Returns a DataFrame with exactly MODEL_FEATURE_COLUMNS (same order as training CSV).
    """
    d = payload.model_dump()
    injured_yesterday = float(max(0.0, min(1.0, _injured_yesterday_float(d.get("injuredYesterday")))))

    sleep_minutes = d.get("sleepMinutes")
    sleep_hours = (
        float(sleep_minutes) / 60.0 if sleep_minutes is not None else DEFAULT_FEATURE_VALUES["sleep_hours"]
    )
    if not math.isfinite(sleep_hours) or sleep_hours <= 0:
        sleep_hours = float(DEFAULT_FEATURE_VALUES["sleep_hours"])
    sleep_hours = float(max(3.0, min(12.0, sleep_hours)))

    steps = max(0.0, _safe_float(d.get("steps"), 0.0))
    distance_m = max(0.0, _safe_float(d.get("distanceMeters"), 0.0))
    daily_distance_km = distance_m / 1000.0 if distance_m > 0 else max(0.0, steps * 0.0008)
    daily_distance_km = float(min(60.0, daily_distance_km))

    active_cal = max(0.0, _safe_float(d.get("activeCalories"), 0.0))
    total_burned_health = max(0.0, _safe_float(d.get("totalCalories"), 0.0))
    bmr = max(0.0, _safe_float(d.get("bmrCalories"), 0.0))
    # totalCalories in daily_health represents burn from Health Connect.
    total_burned = float(
        total_burned_health
        if total_burned_health > 0
        else (bmr + active_cal if (bmr > 0 or active_cal > 0) else DEFAULT_FEATURE_VALUES["total_calories_burned"])
    )
    if total_burned <= 0:
        total_burned = float(DEFAULT_FEATURE_VALUES["total_calories_burned"])
    total_burned = float(min(9000.0, total_burned))

    protein_g = max(0.0, _safe_float(d.get("totalProtein"), 0.0))
    carbs_g = max(0.0, _safe_float(d.get("totalCarbs"), 0.0))
    meals_logged = max(0.0, _safe_float(d.get("mealsLoggedCount"), 0.0))
    intake_sum_logged = max(0.0, _safe_float(d.get("nutritionTotalCalories"), 0.0))
    intake_sum_logged = float(min(8000.0, intake_sum_logged))
    macro_energy = protein_g * 4.0 + carbs_g * 4.0
    # If only protein/carbs are available, estimate missing fat energy conservatively.
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
        estimated_intake_from_macros if estimated_intake_from_macros > 0 else float(DEFAULT_FEATURE_VALUES["daily_calories"])
    )
    if intake_sum_logged > 0:
        daily_calories = float(max(800.0, min(7000.0, intake_sum_logged)))
    if meals_logged > 0 and macro_energy <= 0 and intake_sum_logged <= 0:
        daily_calories = float(DEFAULT_FEATURE_VALUES["daily_calories"] * min(1.25, 0.6 + meals_logged * 0.2))
    daily_calories = float(min(7000.0, max(800.0, daily_calories)))

    workout_intensity = max(0.0, min(240.0, daily_distance_km * 5.5 + active_cal / 40.0))
    sensor_cadence = _safe_float(d.get("avgCadence"), 0.0)
    if sensor_cadence > 0:
        avg_cadence = float(max(120.0, min(200.0, sensor_cadence)))
    elif steps > 0 and daily_distance_km > 0.05:
        est_minutes = max(10.0, workout_intensity)
        avg_cadence = float(max(120.0, min(200.0, steps / est_minutes)))
    else:
        avg_cadence = float(DEFAULT_FEATURE_VALUES["avg_cadence"])

    weight_kg = d.get("weightKg")
    height_cm = d.get("heightCm")
    height_m = 1.75
    if height_cm is not None and _safe_float(height_cm, 0.0) > 100:
        height_m = float(height_cm) / 100.0
    bmi = DEFAULT_FEATURE_VALUES["bmi"]
    if weight_kg is not None and _safe_float(weight_kg, 0.0) > 0:
        bmi = float(weight_kg) / (height_m**2)
    bmi = float(max(15.0, min(45.0, bmi)))

    age_val = float(DEFAULT_FEATURE_VALUES["age"])
    age_raw = d.get("age")
    if age_raw is not None:
        try:
            age_val = float(max(12.0, min(90.0, int(age_raw))))
        except (TypeError, ValueError):
            age_val = float(DEFAULT_FEATURE_VALUES["age"])

    history_injury_count = float(DEFAULT_FEATURE_VALUES["history_injury_count"])
    hist_raw = d.get("historyInjuryCount")
    if hist_raw is None:
        hist_raw = d.get("history_injury_count")
    if hist_raw is not None:
        try:
            history_injury_count = float(max(0.0, min(50.0, int(hist_raw))))
        except (TypeError, ValueError):
            history_injury_count = float(DEFAULT_FEATURE_VALUES["history_injury_count"])

    resting_hr_raw = _safe_float(d.get("restingHeartRate"), 0.0)
    hr_avg = _safe_float(d.get("heartRateAvg"), 0.0)
    hr_min = _safe_float(d.get("heartRateMin"), 0.0)
    if resting_hr_raw > 0:
        resting_hr = resting_hr_raw
    elif hr_min > 0:
        resting_hr = hr_min
    elif hr_avg > 0:
        resting_hr = hr_avg
    else:
        resting_hr = float(DEFAULT_FEATURE_VALUES["resting_hr"])
    resting_hr = float(max(38.0, min(95.0, resting_hr)))

    hrv_rmssd = _safe_float(d.get("hrvRmssd"), 0.0)
    if hrv_rmssd > 0:
        hrv_score = float(max(30.0, min(105.0, hrv_rmssd)))
    elif hr_avg > 0:
        hrv_score = float(max(30.0, min(100.0, 110.0 - resting_hr * 0.65)))
    else:
        hrv_score = float(DEFAULT_FEATURE_VALUES["hrv_score"])

    body_fat_pct = _safe_float(d.get("bodyFatPct"), DEFAULT_FEATURE_VALUES["body_fat_pct"])
    body_fat_pct = float(max(3.0, min(50.0, body_fat_pct)))
    vo2_max = _safe_float(d.get("vo2Max"), DEFAULT_FEATURE_VALUES["vo2_max"])
    vo2_max = float(max(15.0, min(90.0, vo2_max)))

    elevation_gained = _safe_float(d.get("elevationGainedMeters"), DEFAULT_FEATURE_VALUES["elevation_gained_m"])
    elevation_gained = float(max(0.0, min(5000.0, elevation_gained)))
    floors_climbed = _safe_float(d.get("floorsClimbed"), DEFAULT_FEATURE_VALUES["floors_climbed"])
    floors_climbed = float(max(0.0, min(200.0, floors_climbed)))

    sensor_avg_speed = _safe_float(d.get("avgSpeed"), 0.0)
    sensor_max_speed = _safe_float(d.get("maxSpeed"), 0.0)
    if sensor_avg_speed > 0:
        avg_speed = float(max(0.0, min(30.0, sensor_avg_speed)))
    elif daily_distance_km > 0.05 and workout_intensity > 5:
        avg_speed = float(max(0.0, min(30.0, daily_distance_km / (workout_intensity / 60.0))))
    else:
        avg_speed = float(DEFAULT_FEATURE_VALUES["avg_speed"])
    max_speed = float(max(0.0, min(40.0, sensor_max_speed))) if sensor_max_speed > 0 else avg_speed * 1.3

    avg_power = _safe_float(d.get("avgPower"), DEFAULT_FEATURE_VALUES["avg_power"])
    avg_power = float(max(0.0, min(800.0, avg_power)))

    respiratory_rate = _safe_float(d.get("respiratoryRate"), DEFAULT_FEATURE_VALUES["respiratory_rate"])
    respiratory_rate = float(max(6.0, min(40.0, respiratory_rate)))
    spo2 = _safe_float(d.get("oxygenSaturation"), DEFAULT_FEATURE_VALUES["spo2"])
    spo2 = float(max(80.0, min(100.0, spo2)))

    partial: dict = {
        "bmi": float(bmi),
        "age": age_val,
        "body_fat_pct": body_fat_pct,
        "vo2_max": vo2_max,
        "history_injury_count": history_injury_count,
        "injured_yesterday": injured_yesterday,
        "daily_distance_km": float(daily_distance_km),
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
        "resting_hr": float(resting_hr),
        "respiratory_rate": respiratory_rate,
        "spo2": spo2,
        "nutrition_intake_calories": float(nutrition_intake_calories),
        "daily_calories": float(daily_calories),
        "total_calories_burned": float(total_burned),
        "stress_level": _stress_to_model_scale(d.get("stressLevel")),
        "muscle_soreness": _soreness_to_model_scale(d.get("muscleSoreness")),
        "energy_level": _energy_to_model_scale(d.get("energyLevel")),
        "_active_calories": active_cal,
        "_bmr_calories": bmr,
    }

    derived = compute_derived_features(partial)
    partial.update(derived)
    partial.pop("_active_calories", None)
    partial.pop("_bmr_calories", None)

    partial["calorie_balance"] = float(partial["daily_calories"] - partial["total_calories_burned"])
    # Proxy sequential features for serving when only snapshot data is available.
    partial["acwr_ratio_ma7"] = float(partial["acwr_ratio"])
    partial["acwr_ratio_std21"] = float(
        max(
            0.02,
            min(
                0.8,
                abs(partial["acwr_ratio"] - 1.0) * 0.35 + abs(partial["hrv_drop"]) * 0.012,
            ),
        )
    )
    partial["sleep_hours_ma7"] = float(partial["sleep_hours"])
    partial["sleep_hours_std21"] = float(max(0.05, min(2.0, abs(8.0 - partial["sleep_hours"]) * 0.45)))

    partial["load_recovery_imbalance"] = float(partial["acwr_ratio"] * partial["sleep_debt_3d"])
    partial["speed_intensity_ratio"] = float(
        min(5.0, partial["max_speed"] / (partial["avg_speed"] + 0.1))
    )

    out: dict[str, float] = {}
    for col in MODEL_FEATURE_COLUMNS:
        val = partial.get(col)
        if val is None or (isinstance(val, float) and not math.isfinite(val)):
            val = DEFAULT_FEATURE_VALUES[col]
        out[col] = float(val)

    frame = pd.DataFrame([out], columns=MODEL_FEATURE_COLUMNS)
    return frame.astype("float64").fillna(pd.Series(DEFAULT_FEATURE_VALUES))
