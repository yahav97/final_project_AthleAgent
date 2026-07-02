"""Field groups used for same-day data-quality scoring."""

# Request fields checked for missing/null/zero (each hit lowers confidence).
SAME_DAY_MEASUREMENT_FIELDS: tuple[str, ...] = (
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

# Optional body metrics: penalized only when the client sends 0 or NaN.
OPTIONAL_PROFILE_FIELDS: tuple[str, ...] = (
    "weightKg",
    "heightCm",
    "bodyFatPct",
    "vo2Max",
)

# Marker in weak_fields when yesterday nutrition used population averages.
NUTRITION_IMPUTED_FLAG: str = "nutrition_imputed"

# Per-field penalty for missing/null/zero measurements or weak profile values (0–1 scale).
ZERO_OR_MISSING_PENALTY: float = 0.08
NUTRITION_IMPUTED_PENALTY: float = 0.12

# Backward-compatible aliases (prefer the names above in new code/docs).
MEASUREMENT_FIELDS = SAME_DAY_MEASUREMENT_FIELDS
PROFILE_FIELDS = OPTIONAL_PROFILE_FIELDS
