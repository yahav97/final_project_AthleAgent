"""Same-day payload completeness scoring."""

from __future__ import annotations

from schemas.inference import InjuryPredictionRequest
from services.preprocessing.constants import (
    MEASUREMENT_FIELDS,
    NUTRITION_IMPUTED_PENALTY,
    PROFILE_FIELDS,
    ZERO_OR_MISSING_PENALTY,
)
from services.preprocessing.helpers import is_explicit_zero_or_nan


def calculate_data_quality_score(
    payload: InjuryPredictionRequest,
) -> dict[str, float | list[str] | bool]:
    """
    Score same-day input strength for prediction confidence.

    Policy:
    - Frontend payloads are trusted; absent fields are not penalized.
    - Fields explicitly sent as 0 or NaN reduce confidence.
    - Imputed nutrition history is flagged separately.
    - Historical gaps are handled in ``confidence`` (not here).
    """
    payload_dict = payload.model_dump()
    weak_fields: list[str] = []

    for field in MEASUREMENT_FIELDS + PROFILE_FIELDS:
        raw = payload_dict.get(field)
        if raw is not None and is_explicit_zero_or_nan(raw):
            weak_fields.append(field)

    if payload_dict.get("nutritionImputed"):
        weak_fields.append("nutrition_imputed")

    penalty = ZERO_OR_MISSING_PENALTY * len(
        [f for f in weak_fields if f in MEASUREMENT_FIELDS + PROFILE_FIELDS]
    )
    if "nutrition_imputed" in weak_fields:
        penalty += NUTRITION_IMPUTED_PENALTY

    score = max(0.0, min(1.0, 1.0 - penalty))

    return {
        "score": float(score),
        "weak_fields": weak_fields,
        "hard_missing": [],
        "sensitive_missing": weak_fields,
        "has_hard_blocker": False,
    }
