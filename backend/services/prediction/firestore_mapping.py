"""Build InjuryPredictionRequest from Firestore daily snapshot."""

from __future__ import annotations

from typing import Any

from schemas.inference import InjuryPredictionRequest
from services.field_transforms import (
    age_from_profile,
    heart_rate_avg_from_doc,
    injured_yesterday_from_docs,
)


def _wearable_value(doc: dict[str, Any], field_name: str) -> Any:
    """Return a numeric wearable field; Firestore missing keys become 0."""
    value = doc.get(field_name)
    return 0 if value is None else value


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
        historyInjuryCount=profile.get("historyInjuryCount"),
        injuredYesterday=injured_yesterday_from_docs(checkins, health_today),
        sleepMinutes=_wearable_value(health_today, "sleepMinutes"),
        steps=_wearable_value(health_yesterday, "steps"),
        distanceMeters=_wearable_value(health_yesterday, "distanceMeters"),
        activeCalories=_wearable_value(health_yesterday, "activeCalories"),
        totalCalories=_wearable_value(health_yesterday, "totalCalories"),
        heartRateAvg=heart_rate_avg_from_doc(health_yesterday),
        heartRateMax=_wearable_value(health_yesterday, "heartRateMax"),
        heartRateMin=_wearable_value(health_yesterday, "heartRateMin"),
        weightKg=health_yesterday.get("weightKg"),
        heightCm=health_yesterday.get("heightCm"),
        bmrCalories=_wearable_value(health_yesterday, "bmrCalories"),
        hrvRmssd=health_yesterday.get("hrvRmssd"),
        restingHeartRate=_wearable_value(health_yesterday, "restingHeartRate"),
        bodyFatPct=health_yesterday.get("bodyFatPct"),
        vo2Max=health_yesterday.get("vo2Max"),
        elevationGainedMeters=health_yesterday.get("elevationGainedMeters"),
        floorsClimbed=_wearable_value(health_yesterday, "floorsClimbed"),
        avgSpeed=health_yesterday.get("avgSpeed"),
        maxSpeed=health_yesterday.get("maxSpeed"),
        avgPower=health_yesterday.get("avgPower"),
        avgCadence=health_yesterday.get("avgCadence"),
        respiratoryRate=health_yesterday.get("respiratoryRate"),
        oxygenSaturation=health_yesterday.get("oxygenSaturation"),
        energyLevel=checkins.get("energyLevel"),
        muscleSoreness=checkins.get("muscleSoreness"),
        stressLevel=checkins.get("stressLevel"),
        totalProtein=nutrition_yesterday.get("totalProtein"),
        totalCarbs=nutrition_yesterday.get("totalCarbs"),
        mealsLoggedCount=nutrition_yesterday.get("mealsLoggedCount"),
        nutritionTotalCalories=nutrition_yesterday.get("totalCalories"),
    )
