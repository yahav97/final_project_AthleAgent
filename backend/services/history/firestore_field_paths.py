"""Firestore field projections for inference reads (train-serve contract)."""

from __future__ import annotations

PROFILE_INFERENCE_FIELDS: tuple[str, ...] = (
    "birth_date",
    "historyInjuryCount",
)

DAILY_HEALTH_INFERENCE_FIELDS: tuple[str, ...] = (
    "sleepMinutes",
    "injuredYesterday",
    "steps",
    "distanceMeters",
    "activeCalories",
    "totalCalories",
    "heartRateAvg",
    "heartRateMax",
    "heartRateMin",
    "weightKg",
    "heightCm",
    "bmrCalories",
    "hrvRmssd",
    "restingHeartRate",
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
)

DAILY_CHECKIN_INFERENCE_FIELDS: tuple[str, ...] = (
    "energyLevel",
    "muscleSoreness",
    "stressLevel",
    "injuredYesterday",
)

DAILY_NUTRITION_INFERENCE_FIELDS: tuple[str, ...] = (
    "totalProtein",
    "totalCarbs",
    "mealsLoggedCount",
    "totalCalories",
)

INFERENCE_FIELD_PATHS: tuple[str, ...] = tuple(
    sorted(
        {
            *PROFILE_INFERENCE_FIELDS,
            *DAILY_HEALTH_INFERENCE_FIELDS,
            *DAILY_CHECKIN_INFERENCE_FIELDS,
            *DAILY_NUTRITION_INFERENCE_FIELDS,
        }
    )
)
