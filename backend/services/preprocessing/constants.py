"""Field groups used for data-quality scoring."""

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
