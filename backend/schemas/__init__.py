"""Pydantic schemas for API requests and responses."""

from .inference import (
    AthleteData,
    DailyPredictionTriggerRequest,
    InjuryPredictionRequest,
    InjuryPredictionResponse,
    SimpleData,
)

__all__ = [
    "AthleteData",
    "DailyPredictionTriggerRequest",
    "InjuryPredictionRequest",
    "InjuryPredictionResponse",
    "SimpleData",
]
