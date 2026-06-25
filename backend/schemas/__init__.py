"""Pydantic schemas for API requests and responses."""

from .inference import (
    DailyPredictionTriggerRequest,
    InjuryPredictionRequest,
    InjuryPredictionResponse,
    SimpleData,
)

__all__ = [
    "DailyPredictionTriggerRequest",
    "InjuryPredictionRequest",
    "InjuryPredictionResponse",
    "SimpleData",
]
