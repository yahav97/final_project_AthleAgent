"""Field groups used for data-quality scoring."""

# Sensor / load / recovery measurements: 0 or missing lowers confidence.
MEASUREMENT_FIELDS: tuple[str, ...] = (
    "sleepMinutes",
    "steps",
    "distanceMeters",
    "activeCalories",
    "heartRateAvg",
    "hrvRmssd",
    "restingHeartRate",
    "totalCalories",
    "bmrCalories",
    "nutritionTotalCalories",
    "totalProtein",
    "totalCarbs",
)

# Optional profile / body metrics.
PROFILE_FIELDS: tuple[str, ...] = (
    "weightKg",
    "heightCm",
    "bodyFatPct",
    "vo2Max",
)

# Per-field penalty for missing/null/zero measurements or weak profile values (0–1 scale).
ZERO_OR_MISSING_PENALTY: float = 0.08
NUTRITION_IMPUTED_PENALTY: float = 0.12
