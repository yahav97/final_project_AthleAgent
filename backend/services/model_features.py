"""Feature column contract for injury_model.pkl (must match ML_model/athlete_injury_data.csv)."""

# Production contract: these columns are passed to the estimator after preprocessing (currently 24).
# Training CSV rows omit the four rolling-summary columns below; `ML_model/train_model.add_sequential_features`
# recomputes them from per-athlete history so labels align with the synthetic pipeline.
TRAINING_CSV_EXCLUDE_COLUMNS: tuple[str, ...] = (
    "acwr_ratio_ma7",
    "acwr_ratio_std21",
    "sleep_hours_ma7",
    "sleep_hours_std21",
)

MODEL_FEATURE_COLUMNS: list[str] = [
    "bmi",
    # Survey on today's daily_health: injury on previous calendar day (Firestore injuredYesterday)
    "injured_yesterday",
    "daily_distance_km",
    "workout_intensity_minutes",
    "avg_cadence",
    "sleep_hours",
    "hrv_score",
    "resting_hr",
    # daily_nutrition aggregate (distinct from daily_health totalCalories = burn)
    "nutrition_intake_calories",
    "daily_calories",
    "total_calories_burned",
    "stress_level",
    "muscle_soreness",
    # daily_checkins.energyLevel (0–100 UI → 1–10)
    "energy_level",
    "acute_load_7d",
    "chronic_load_21d",
    "acwr_ratio",
    "acwr_ratio_ma7",
    "acwr_ratio_std21",
    "calorie_balance",
    "sleep_hours_ma7",
    "sleep_hours_std21",
    "sleep_debt_3d",
    "hrv_drop",
]

TRAINING_BASE_FEATURE_COLUMNS: tuple[str, ...] = tuple(
    c for c in MODEL_FEATURE_COLUMNS if c not in TRAINING_CSV_EXCLUDE_COLUMNS
)

# Population-style medians for imputation when the mobile payload is sparse
DEFAULT_FEATURE_VALUES: dict[str, float] = {
    "bmi": 23.5,
    "injured_yesterday": 0.0,
    "daily_distance_km": 3.5,
    "workout_intensity_minutes": 45.0,
    "avg_cadence": 168.0,
    "sleep_hours": 7.0,
    "hrv_score": 62.0,
    "resting_hr": 54.0,
    "nutrition_intake_calories": 2500.0,
    "daily_calories": 2500.0,
    "total_calories_burned": 2450.0,
    "stress_level": 5.0,
    "muscle_soreness": 5.0,
    "energy_level": 5.0,
    "acute_load_7d": 4.5,
    "chronic_load_21d": 5.1,
    "acwr_ratio": 1.0,
    "acwr_ratio_ma7": 1.0,
    "acwr_ratio_std21": 0.18,
    "calorie_balance": 0.0,
    "sleep_hours_ma7": 7.0,
    "sleep_hours_std21": 0.9,
    "sleep_debt_3d": 1.0,
    "hrv_drop": 0.0,
}
