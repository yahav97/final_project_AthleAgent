"""Shared parsing and normalization for Firestore / API health fields."""

from __future__ import annotations

from typing import Any, Mapping

from services.model_features import DEFAULT_FEATURE_VALUES

STEPS_TO_KM = 0.0008
RESTING_HR_MIN = 38.0
RESTING_HR_MAX = 95.0
DEFAULT_RESTING_HR = float(DEFAULT_FEATURE_VALUES["resting_hr"])


def parse_injured_yesterday_flag(raw: object) -> int | None:
    """Parse bool/int injuredYesterday to 0 or 1; None when input is None or invalid."""
    if raw is None:
        return None
    if raw is True:
        return 1
    if raw is False:
        return 0
    try:
        return 1 if int(raw) else 0
    except (TypeError, ValueError):
        return None


def injured_yesterday_for_request(raw: object) -> int | None:
    """Coerce injuredYesterday for InjuryPredictionRequest (invalid → None)."""
    if raw is None:
        return None
    if raw is True:
        return 1
    if raw is False:
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def injured_yesterday_as_feature(raw: object) -> float:
    """Model feature 0/1; missing or invalid → population default."""
    parsed = parse_injured_yesterday_flag(raw)
    if parsed is None:
        return float(DEFAULT_FEATURE_VALUES["injured_yesterday"])
    return float(parsed)


def injured_yesterday_from_doc(data: Mapping[str, Any]) -> int | None:
    """Read injuredYesterday from a Firestore doc; invalid values → 0."""
    raw = data.get("injuredYesterday")
    if raw is None:
        raw = data.get("injured_yesterday")
    if raw is None:
        return None
    parsed = parse_injured_yesterday_flag(raw)
    return 0 if parsed is None else parsed


def daily_distance_km(distance_meters: float, steps: float) -> float:
    distance_m = max(0.0, distance_meters)
    if distance_m > 0:
        return distance_m / 1000.0
    return max(0.0, steps) * STEPS_TO_KM


def daily_distance_km_from_doc(doc: Mapping[str, Any]) -> float:
    return daily_distance_km(
        float(doc.get("distanceMeters") or 0.0),
        float(doc.get("steps") or 0.0),
    )


def resting_hr(
    resting: float,
    hr_min: float,
    hr_avg: float,
    *,
    default: float = DEFAULT_RESTING_HR,
) -> float:
    """RestingHeartRate → heartRateMin → heartRateAvg, clamped to sane range."""
    if resting > 0:
        value = resting
    elif hr_min > 0:
        value = hr_min
    elif hr_avg > 0:
        value = hr_avg
    else:
        return float(default)
    return float(max(RESTING_HR_MIN, min(RESTING_HR_MAX, value)))


def resting_hr_from_doc(doc: Mapping[str, Any]) -> float:
    return resting_hr(
        float(doc.get("restingHeartRate") or 0.0),
        float(doc.get("heartRateMin") or 0.0),
        float(doc.get("heartRateAvg") or 0.0),
    )


def hrv_proxy_from_resting_hr(resting_hr_bpm: float) -> float:
    return float(max(30.0, min(100.0, 110.0 - resting_hr_bpm * 0.65)))
