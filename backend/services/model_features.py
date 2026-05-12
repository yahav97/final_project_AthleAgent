"""Feature column contract for injury_model.pkl (must match ML_model/athlete_injury_data.csv)."""

# Training CSV rows omit the four rolling-summary columns below; `ML_model/train_model.add_sequential_features`
# recomputes them from per-athlete history so labels align with the synthetic pipeline.
TRAINING_CSV_EXCLUDE_COLUMNS: tuple[str, ...] = (
    "acwr_ratio_ma7",
    "sleep_hours_ma7",
)

MODEL_FEATURE_COLUMNS: list[str] = [
    # --- Static / Profile ---
    "bmi",
    "age",
    "body_fat_pct",
    "vo2_max",
    # --- History / State ---
    "history_injury_count",
    "injured_yesterday",
    # --- Training Load ---
    "daily_distance_km",
    "workout_intensity_minutes",
    "avg_cadence",
    "elevation_gained_m",
    "floors_climbed",
    "avg_speed",
    "max_speed",
    "avg_power",
    "active_calories_burned",
    # --- Recovery / Physiology ---
    "sleep_hours",
    "hrv_score",
    "resting_hr",
    "respiratory_rate",
    "spo2",
    # --- Nutrition / Energy ---
    "nutrition_intake_calories",
    "daily_calories",
    "total_calories_burned",
    # --- Subjective (manual input) ---
    "stress_level",
    "muscle_soreness",
    "energy_level",
    # --- Engineered / Derived ---
    "acute_load_7d",
    "chronic_load_21d",
    "acwr_ratio",
    "acwr_ratio_ma7",
    "calorie_balance",
    "sleep_hours_ma7",
    "sleep_debt_3d",
    "hrv_drop",
    "load_recovery_imbalance",
    "speed_intensity_ratio",
]

TRAINING_BASE_FEATURE_COLUMNS: tuple[str, ...] = tuple(
    c for c in MODEL_FEATURE_COLUMNS if c not in TRAINING_CSV_EXCLUDE_COLUMNS
)

# Population-style medians for imputation when the mobile payload is sparse.
# New sensor features (body_fat, vo2_max, spo2, etc.) use neutral medians so
# athletes without those sensors get a no-signal baseline.
DEFAULT_FEATURE_VALUES: dict[str, float] = {
    "bmi": 23.5,
    "age": 28.0,
    "body_fat_pct": 16.0,
    "vo2_max": 48.0,
    "history_injury_count": 0.0,
    "injured_yesterday": 0.0,
    "daily_distance_km": 3.5,
    "workout_intensity_minutes": 45.0,
    "avg_cadence": 168.0,
    "elevation_gained_m": 50.0,
    "floors_climbed": 5,
    "avg_speed": 8.0,
    "max_speed": 11.0,
    "avg_power": 0.0,
    "active_calories_burned": 350.0,
    "sleep_hours": 7.0,
    "hrv_score": 62.0,
    "resting_hr": 54.0,
    "respiratory_rate": 15.0,
    "spo2": 97.0,
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
    "calorie_balance": 0.0,
    "sleep_hours_ma7": 7.0,
    "sleep_debt_3d": 1.0,
    "hrv_drop": 0.0,
    "load_recovery_imbalance": 1.0,
    "speed_intensity_ratio": 1.3,
}
