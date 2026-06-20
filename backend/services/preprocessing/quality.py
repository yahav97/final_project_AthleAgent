"""Same-day payload completeness scoring."""

from __future__ import annotations

from schemas.inference import InjuryPredictionRequest
from services.preprocessing.constants import HARD_FIELDS, SENSITIVE_FIELDS
from services.preprocessing.helpers import is_present


def calculate_data_quality_score(payload: InjuryPredictionRequest) -> dict[str, object]:
    """
    Score current-day payload completeness and report hard-missing conditions.

    Score range: 0.0 - 1.0
    - tolerant missing fields do not reduce score
    - sensitive missing fields reduce score
    - hard requirements trigger red flag
    """
    payload_dict = payload.model_dump()
    hard_missing = [field for field in HARD_FIELDS if not is_present(payload_dict.get(field))]
    sensitive_missing = [
        field for field in SENSITIVE_FIELDS if not is_present(payload_dict.get(field))
    ]

    has_load_signal = is_present(payload_dict.get("steps")) or is_present(
        payload_dict.get("distanceMeters")
    )
    has_recovery_signal = is_present(payload_dict.get("sleepMinutes")) or (
        is_present(payload_dict.get("stressLevel")) and is_present(payload_dict.get("muscleSoreness"))
    )
    if not has_load_signal:
        hard_missing.append("load_signal")
    if not has_recovery_signal:
        hard_missing.append("recovery_signal")

    sensitive_penalty = 0.12 * len(sensitive_missing)
    score = max(0.0, min(1.0, 1.0 - sensitive_penalty))
    if hard_missing:
        score = min(score, 0.25)

    return {
        "score": float(score),
        "hard_missing": hard_missing,
        "sensitive_missing": sensitive_missing,
        "has_hard_blocker": bool(hard_missing),
    }
