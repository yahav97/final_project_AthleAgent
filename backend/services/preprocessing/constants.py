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

# Survey scales: missing lowers confidence; 0 is a valid UI value.
SURVEY_FIELDS: tuple[str, ...] = (
    "stressLevel",
    "muscleSoreness",
    "energyLevel",
)

# Optional profile / body metrics.
PROFILE_FIELDS: tuple[str, ...] = (
    "weightKg",
    "heightCm",
    "bodyFatPct",
    "vo2Max",
)

# Per-field penalty when an explicitly sent value is zero or NaN (0–1 scale).
ZERO_OR_MISSING_PENALTY: float = 0.08
NUTRITION_IMPUTED_PENALTY: float = 0.12
