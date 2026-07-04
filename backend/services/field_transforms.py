"""Shared parsing and normalization for Firestore / API health fields."""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any, Mapping

from config import settings
from utils.exceptions import ValidationError

STEPS_TO_KM = 0.0008
DAYS_PER_YEAR = 365.0
DEFAULT_RESTING_HR = 0.0


def parse_date_key(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def float_from_doc(doc: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    return float(doc.get(key) or default)


def age_from_birth_date(birth_date: object, *, as_of_date: str | None = None) -> float | None:
    """Compute decimal age in years from ``birth_date`` (yyyy-MM-dd) as of ``as_of_date``."""
    if birth_date is None:
        return None
    birth_str = str(birth_date).strip()
    if not birth_str:
        return None
    birth = parse_date_key(birth_str[:10])
    if birth is None:
        return None

    ref = parse_date_key(as_of_date) if as_of_date else date.today()
    if ref is None:
        ref = date.today()

    if birth > ref:
        return None
    return round(float((ref - birth).days) / DAYS_PER_YEAR, 2)


def age_from_profile(profile: Mapping[str, Any], *, as_of_date: str | None = None) -> float | None:
    """Compute model age from Firestore profile ``birth_date``."""
    birth_raw = profile.get("birth_date")
    if birth_raw is None:
        return None
    return age_from_birth_date(birth_raw, as_of_date=as_of_date)


def resolve_model_age(age_raw: object) -> float:
    """Resolve model age from profile ``birth_date`` or ``settings.PROFILE_DEFAULT_AGE``."""
    if age_raw is None:
        return float(settings.PROFILE_DEFAULT_AGE)
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


def injured_yesterday_from_docs(*docs: Mapping[str, Any]) -> int | None:
    """Read ``injuredYesterday`` from the first doc that has it (checkins, then health)."""
    for doc in docs:
        raw = doc.get("injuredYesterday")
        if raw is not None:
            return parse_injured_yesterday_flag(raw)
    return None


def heart_rate_avg_from_doc(doc: Mapping[str, Any]) -> object | None:
    return doc.get("heartRateAvg")


def daily_distance_km(distance_meters: float, steps: float) -> float:
    distance_m = max(0.0, distance_meters)
    if distance_m > 0:
        return distance_m / 1000.0
    return max(0.0, steps) * STEPS_TO_KM


def daily_distance_km_from_doc(doc: Mapping[str, Any]) -> float:
    return daily_distance_km(
        float_from_doc(doc, "distanceMeters"),
        float_from_doc(doc, "steps"),
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
        float_from_doc(doc, "restingHeartRate"),
        float_from_doc(doc, "heartRateMin"),
        float_from_doc(doc, "heartRateAvg"),
    )


def hrv_proxy_from_resting_hr(resting_hr_bpm: float) -> float:
    return float(max(30.0, min(100.0, 110.0 - resting_hr_bpm * 0.65)))
