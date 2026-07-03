"""Build InjuryPredictionRequest from Firestore daily snapshot."""

from __future__ import annotations

from typing import Any

from schemas.inference import InjuryPredictionRequest
from services.field_transforms import (
    age_from_profile,
    first_doc_value,
    heart_rate_avg_from_doc,
    injured_yesterday_from_docs,
)

# Alternative Firestore keys for the same logical field (camelCase / snake_case).
FirestoreFieldNames = tuple[str, ...]

SLEEP_MINUTES_FIELDS: FirestoreFieldNames = ("sleepMinutes", "sleep_minutes")
STEPS_FIELDS: FirestoreFieldNames = ("steps", "daily_steps")
DISTANCE_FIELDS: FirestoreFieldNames = (
    "distanceMeters",
    "distance_meters",
    "daily_distance_meters",
)
ACTIVE_CALORIES_FIELDS: FirestoreFieldNames = (
    "activeCalories",
    "active_calories",
    "active_calories_burned",
)
TOTAL_CALORIES_FIELDS: FirestoreFieldNames = (
    "totalCalories",
    "total_calories",
    "daily_calories",
)
HEART_RATE_MAX_FIELDS: FirestoreFieldNames = ("heartRateMax", "heart_rate_max")
HEART_RATE_MIN_FIELDS: FirestoreFieldNames = ("heartRateMin", "heart_rate_min")
WEIGHT_FIELDS: FirestoreFieldNames = ("weightKg", "weight_kg")
HEIGHT_FIELDS: FirestoreFieldNames = ("heightCm", "height_cm")
BMR_FIELDS: FirestoreFieldNames = ("bmrCalories", "bmr_calories")
HRV_FIELDS: FirestoreFieldNames = ("hrvRmssd", "hrv_rmssd", "hrv_score")
RESTING_HR_FIELDS: FirestoreFieldNames = (
    "restingHeartRate",
    "resting_heart_rate",
    "resting_hr",
)
BODY_FAT_FIELDS: FirestoreFieldNames = ("bodyFatPct", "body_fat_pct")
VO2_MAX_FIELDS: FirestoreFieldNames = ("vo2Max", "vo2_max")
ELEVATION_FIELDS: FirestoreFieldNames = ("elevationGainedMeters", "elevation_gained_meters")
FLOORS_FIELDS: FirestoreFieldNames = ("floorsClimbed", "floors_climbed")
AVG_SPEED_FIELDS: FirestoreFieldNames = ("avgSpeed", "avg_speed")
MAX_SPEED_FIELDS: FirestoreFieldNames = ("maxSpeed", "max_speed")
AVG_POWER_FIELDS: FirestoreFieldNames = ("avgPower", "avg_power")
AVG_CADENCE_FIELDS: FirestoreFieldNames = ("avgCadence", "avg_cadence")
RESPIRATORY_RATE_FIELDS: FirestoreFieldNames = ("respiratoryRate", "respiratory_rate")
OXYGEN_SATURATION_FIELDS: FirestoreFieldNames = (
    "oxygenSaturation",
    "oxygen_saturation",
    "spo2",
)


def read_first_matching_field(
    primary: dict[str, Any],
    fallback: dict[str, Any],
    field_names: FirestoreFieldNames,
    prefer_primary: bool,
) -> Any:
    """Return the first usable value across docs and field-name aliases.

    Non-zero values are preferred over zero (treated as weak / placeholder).
    """
    docs = (primary, fallback) if prefer_primary else (fallback, primary)
    for allow_zero in (False, True):
        for doc in docs:
            for field_name in field_names:
                value = doc.get(field_name)
                if value is None:
                    continue
                if not allow_zero and value == 0:
                    continue
                return value
    return 0


def _field_from_single_doc(doc: dict[str, Any], field_names: FirestoreFieldNames) -> Any:
    """Read a field from one Firestore document (no primary/fallback merge)."""
    return read_first_matching_field(doc, {}, field_names, prefer_primary=True)


# Backward-compatible alias used in tests.
field_from_docs = read_first_matching_field


def injury_prediction_request_from_firestore_snapshot(
    user_id: str,
    date_key: str,
    snapshot: dict[str, Any],
) -> InjuryPredictionRequest:
    """
    Build the same ``InjuryPredictionRequest`` as the production Firestore path.

    Morning prediction merge policy (API date = wake-up day ``D``):
    - Sleep / recovery: ``daily_health/{D}`` only (last night ending this morning).
    - Physical load: ``daily_health/{D-1}`` only (Android sync writes load to prior day).
    - Survey: ``daily_checkins/{D}``.
    - Nutrition: raw ``daily_nutrition/{D-1}`` fields (defaults applied in ``predict_injury_risk``).
    """
    profile = snapshot.get("profile") or {}
    health_today = snapshot.get("daily_health") or {}
    health_yesterday = snapshot.get("daily_health_yesterday") or {}
    checkins = snapshot.get("daily_checkins") or {}
    nutrition_yesterday = snapshot.get("daily_nutrition_yesterday") or {}

    return InjuryPredictionRequest(
        userId=user_id,
        date=date_key,
        age=age_from_profile(profile, as_of_date=date_key),
        historyInjuryCount=first_doc_value(profile, "historyInjuryCount", "history_injury_count"),
        injuredYesterday=injured_yesterday_from_docs(checkins, health_today),
        sleepMinutes=_field_from_single_doc(health_today, SLEEP_MINUTES_FIELDS),
        steps=_field_from_single_doc(health_yesterday, STEPS_FIELDS),
        distanceMeters=_field_from_single_doc(health_yesterday, DISTANCE_FIELDS),
        activeCalories=_field_from_single_doc(health_yesterday, ACTIVE_CALORIES_FIELDS),
        totalCalories=_field_from_single_doc(health_yesterday, TOTAL_CALORIES_FIELDS),
        heartRateAvg=heart_rate_avg_from_doc(health_yesterday),
        heartRateMax=_field_from_single_doc(health_yesterday, HEART_RATE_MAX_FIELDS),
        heartRateMin=_field_from_single_doc(health_yesterday, HEART_RATE_MIN_FIELDS),
        weightKg=_field_from_single_doc(health_yesterday, WEIGHT_FIELDS),
        heightCm=_field_from_single_doc(health_yesterday, HEIGHT_FIELDS),
        bmrCalories=_field_from_single_doc(health_yesterday, BMR_FIELDS),
        hrvRmssd=_field_from_single_doc(health_yesterday, HRV_FIELDS),
        restingHeartRate=_field_from_single_doc(health_yesterday, RESTING_HR_FIELDS),
        bodyFatPct=_field_from_single_doc(health_yesterday, BODY_FAT_FIELDS),
        vo2Max=_field_from_single_doc(health_yesterday, VO2_MAX_FIELDS),
        elevationGainedMeters=_field_from_single_doc(health_yesterday, ELEVATION_FIELDS),
        floorsClimbed=_field_from_single_doc(health_yesterday, FLOORS_FIELDS),
        avgSpeed=_field_from_single_doc(health_yesterday, AVG_SPEED_FIELDS),
        maxSpeed=_field_from_single_doc(health_yesterday, MAX_SPEED_FIELDS),
        avgPower=_field_from_single_doc(health_yesterday, AVG_POWER_FIELDS),
        avgCadence=_field_from_single_doc(health_yesterday, AVG_CADENCE_FIELDS),
        respiratoryRate=_field_from_single_doc(health_yesterday, RESPIRATORY_RATE_FIELDS),
        oxygenSaturation=_field_from_single_doc(health_yesterday, OXYGEN_SATURATION_FIELDS),
        energyLevel=checkins.get("energyLevel"),
        muscleSoreness=checkins.get("muscleSoreness"),
        stressLevel=checkins.get("stressLevel"),
        totalProtein=nutrition_yesterday.get("totalProtein"),
        totalCarbs=nutrition_yesterday.get("totalCarbs"),
        mealsLoggedCount=nutrition_yesterday.get("mealsLoggedCount"),
        nutritionTotalCalories=nutrition_yesterday.get("totalCalories"),
    )
