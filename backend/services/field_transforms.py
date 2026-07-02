"""Shared parsing and normalization for Firestore / API health fields."""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any, Mapping

from utils.exceptions import ValidationError

STEPS_TO_KM = 0.0008
DAYS_PER_YEAR = 365.0
DEFAULT_RESTING_HR = 0.0


def _parse_date_key(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def age_from_birth_date(birth_date: object, *, as_of_date: str | None = None) -> float | None:
    """Compute decimal age in years from ``birth_date`` (yyyy-MM-dd) as of ``as_of_date``."""
    if birth_date is None:
        return None
    birth_str = str(birth_date).strip()
    if not birth_str:
        return None
    birth = _parse_date_key(birth_str[:10])
    if birth is None:
        return None

    ref = _parse_date_key(as_of_date) if as_of_date else date.today()
    if ref is None:
        ref = date.today()

    if birth > ref:
        return None
    return round(float((ref - birth).days) / DAYS_PER_YEAR, 2)


def age_from_profile(profile: Mapping[str, Any], *, as_of_date: str | None = None) -> float | None:
    """Compute model age from Firestore profile ``birth_date`` (or ``birthDate``)."""
    birth_raw = profile.get("birth_date")
    if birth_raw is None:
        birth_raw = profile.get("birthDate")
    if birth_raw is None:
        return None
    return age_from_birth_date(birth_raw, as_of_date=as_of_date)


def resolve_model_age(age_raw: object) -> float:
    """Require athlete age for inference — derived from profile ``birth_date`` at serve time."""
    if age_raw is None:
        raise ValidationError(
            "age is required; set birth_date on user profile",
            code="missing_age",
        )
    try:
        age = float(age_raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            "age is invalid; birth_date must be yyyy-MM-dd",
            code="invalid_age",
        ) from exc
    if not math.isfinite(age):
        raise ValidationError(
            "age is invalid; birth_date must be yyyy-MM-dd",
            code="invalid_age",
        )
    return round(age, 2)


def parse_injured_yesterday_flag(raw: object) -> int | None:
    """Parse bool/int injuredYesterday to 0 or 1; None when input is None or invalid."""
    if raw is None:
        return None
    if raw is True:
        return 1
    if raw is False:
        return 0
    if isinstance(raw, (int, float, str)):
        try:
            return 1 if int(raw) else 0
        except (TypeError, ValueError):
            return None
    return None


def injured_yesterday_for_request(raw: object) -> int | None:
    """Coerce injuredYesterday for InjuryPredictionRequest (invalid → None)."""
    if raw is None:
        return None
    if raw is True:
        return 1
    if raw is False:
        return 0
    if isinstance(raw, (int, float, str)):
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None
    return None


def injured_yesterday_as_feature(raw: object) -> float:
    """Model feature 0/1; missing or invalid → 0."""
    parsed = parse_injured_yesterday_flag(raw)
    if parsed is None:
        return 0.0
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
    """RestingHeartRate → heartRateMin → heartRateAvg; missing chain → default (0)."""
    if resting > 0:
        return float(resting)
    if hr_min > 0:
        return float(hr_min)
    if hr_avg > 0:
        return float(hr_avg)
    return float(default)


def resting_hr_from_doc(doc: Mapping[str, Any]) -> float:
    return resting_hr(
        float(doc.get("restingHeartRate") or 0.0),
        float(doc.get("heartRateMin") or 0.0),
        float(doc.get("heartRateAvg") or 0.0),
    )


def hrv_proxy_from_resting_hr(resting_hr_bpm: float) -> float:
    return float(max(30.0, min(100.0, 110.0 - resting_hr_bpm * 0.65)))
