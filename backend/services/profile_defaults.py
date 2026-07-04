"""Profile field imputation when Firestore user profile is incomplete."""

from __future__ import annotations

from schemas.inference import InjuryPredictionRequest


def resolve_request_age(payload: InjuryPredictionRequest) -> InjuryPredictionRequest:
    """Flag imputed age when ``birth_date`` was missing on the profile snapshot."""
    if payload.age is not None:
        return payload
    return payload.model_copy(update={"ageImputed": True})
