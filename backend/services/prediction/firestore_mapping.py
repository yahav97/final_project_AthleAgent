"""Build InjuryPredictionRequest from Firestore daily snapshot."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from schemas.inference import InjuryPredictionRequest
from services.field_transforms import injured_yesterday_for_request
from services.history_service import _to_date_key, merge_nutrition_with_history


def firestore_doc_heartrate_avg(doc: dict[str, Any]) -> Any:
    """Prefer ``heartRateAvg``; Firestore samples also used ``avgHeartRate``."""
    if not doc:
        return None
    value = doc.get("heartRateAvg")
    if value is not None:
        return value
    return doc.get("avgHeartRate")


def field_from_docs(
    primary: dict[str, Any],
    fallback: dict[str, Any],
    field_options: list[str],
    prefer_primary: bool,
) -> Any:
    """Read the first non-null field name; order of docs depends on ``prefer_primary``."""
    docs = (primary, fallback) if prefer_primary else (fallback, primary)
    for doc in docs:
        for field in field_options:
            value = doc.get(field)
            if value is not None and value != 0:
                return value
    for doc in docs:
        for field in field_options:
            value = doc.get(field)
            if value is not None:
                return value
    return 0


def injury_prediction_request_from_firestore_snapshot(
    user_id: str,
    date_key: str,
    snapshot: dict[str, Any],
) -> InjuryPredictionRequest:
    """
    Build the same ``InjuryPredictionRequest`` as the production Firestore path.

    Morning prediction merge policy (API date = wake-up day ``D``):
    - Sleep / recovery: ``daily_health/{D}`` only (last night ending this morning).
    - Physical load: ``daily_health/{D-1}`` first, fallback ``{D}`` (legacy combined sync).
    - Survey: ``daily_checkins/{D}``.
    - Nutrition: ``daily_nutrition/{D-1}`` + backfill from earlier days.
    """
    profile = snapshot.get("profile") or {}
    health_today = snapshot.get("daily_health") or {}
    health_yesterday = snapshot.get("daily_health_yesterday") or {}
    checkins = snapshot.get("daily_checkins") or {}
    nutrition_raw = snapshot.get("daily_nutrition_yesterday") or {}
    yesterday_key = (_to_date_key(date_key) - timedelta(days=1)).strftime("%Y-%m-%d")
    nutrition = merge_nutrition_with_history(user_id, yesterday_key, nutrition_raw)

    hist_profile = profile.get("historyInjuryCount")
    if hist_profile is None:
        hist_profile = profile.get("history_injury_count")

    injured_raw = checkins.get("injuredYesterday")
    if injured_raw is None:
        injured_raw = checkins.get("injured_yesterday")
    if injured_raw is None:
        injured_raw = health_today.get("injuredYesterday")
    if injured_raw is None:
        injured_raw = health_today.get("injured_yesterday")

    def today_only(field_options: list[str]) -> Any:
        return field_from_docs(health_today, {}, field_options, prefer_primary=True)

    def yesterday_then_today(field_options: list[str]) -> Any:
        return field_from_docs(health_yesterday, health_today, field_options, prefer_primary=True)

    hr_avg = firestore_doc_heartrate_avg(health_yesterday)
    if hr_avg is None:
        hr_avg = firestore_doc_heartrate_avg(health_today)

    return InjuryPredictionRequest(
        userId=user_id,
        date=date_key,
        age=profile.get("age"),
        historyInjuryCount=hist_profile,
        injuredYesterday=injured_yesterday_for_request(injured_raw),
        sleepMinutes=today_only(["sleepMinutes", "sleep_minutes"]),
        steps=yesterday_then_today(["steps", "daily_steps"]),
        distanceMeters=yesterday_then_today(["distanceMeters", "distance_meters", "daily_distance_meters"]),
        activeCalories=yesterday_then_today(["activeCalories", "active_calories", "active_calories_burned"]),
        totalCalories=yesterday_then_today(["totalCalories", "total_calories", "daily_calories"]),
        heartRateAvg=hr_avg,
        heartRateMax=yesterday_then_today(["heartRateMax", "heart_rate_max"]),
        heartRateMin=yesterday_then_today(["heartRateMin", "heart_rate_min"]),
        weightKg=yesterday_then_today(["weightKg", "weight_kg"]),
        heightCm=yesterday_then_today(["heightCm", "height_cm"]),
        bmrCalories=yesterday_then_today(["bmrCalories", "bmr_calories"]),
        hrvRmssd=yesterday_then_today(["hrvRmssd", "hrv_rmssd", "hrv_score"]),
        restingHeartRate=yesterday_then_today(["restingHeartRate", "resting_heart_rate", "resting_hr"]),
        bodyFatPct=yesterday_then_today(["bodyFatPct", "body_fat_pct"]),
        vo2Max=yesterday_then_today(["vo2Max", "vo2_max"]),
        elevationGainedMeters=yesterday_then_today(["elevationGainedMeters", "elevation_gained_meters"]),
        floorsClimbed=yesterday_then_today(["floorsClimbed", "floors_climbed"]),
        avgSpeed=yesterday_then_today(["avgSpeed", "avg_speed"]),
        maxSpeed=yesterday_then_today(["maxSpeed", "max_speed"]),
        avgPower=yesterday_then_today(["avgPower", "avg_power"]),
        avgCadence=yesterday_then_today(["avgCadence", "avg_cadence"]),
        respiratoryRate=yesterday_then_today(["respiratoryRate", "respiratory_rate"]),
        oxygenSaturation=yesterday_then_today(["oxygenSaturation", "oxygen_saturation", "spo2"]),
        energyLevel=checkins.get("energyLevel"),
        muscleSoreness=checkins.get("muscleSoreness"),
        stressLevel=checkins.get("stressLevel"),
        totalProtein=nutrition.get("totalProtein"),
        totalCarbs=nutrition.get("totalCarbs"),
        mealsLoggedCount=nutrition.get("mealsLoggedCount"),
        nutritionTotalCalories=nutrition.get("totalCalories"),
    )
