"""Injury risk prediction HTTP routes."""

from fastapi import APIRouter, HTTPException

from config import settings
from ml.model_loader import get_model_status
from schemas.inference import (
    DailyPredictionTriggerRequest,
    InjuryPredictionResponse,
    SimpleData,
)
from services.prediction_service import (
    persist_prediction_result_or_raise,
    predict_injury_risk_from_firestore,
)
from utils.request_context import user_id_var

router = APIRouter(tags=["Prediction"])


@router.post("/test_predict")
def test_predict_injury(data: SimpleData):
    """Return a fixed mock payload for UI/API smoke usage.

    Args:
        data: Minimal request containing a user identifier.

    Returns:
        dict: Stable mock inference payload.
    """
    if not settings.ENABLE_TEST_PREDICT_ENDPOINT:
        raise HTTPException(
            status_code=404,
            detail="Test endpoint disabled. Set ENABLE_TEST_PREDICT_ENDPOINT=true.",
        )
    return {
        "user_id": data.user_id,
        "risk_percentage": settings.TEST_PREDICT_MOCK_RISK_PERCENTAGE,
        "risk_level": "High",
        "message": "This is a mock response for Android UI testing",
    }


@router.post("/predict/daily", response_model=InjuryPredictionResponse)
def predict_injury_daily(trigger: DailyPredictionTriggerRequest) -> InjuryPredictionResponse:
    """
    Minimal trigger endpoint: frontend sends only userId/date; backend loads all
    relevant daily data directly from Firestore and runs production inference.
    """
    user_id_var.set(trigger.userId)
    result = predict_injury_risk_from_firestore(trigger.userId, trigger.date)
    persist_prediction_result_or_raise(
        trigger.userId,
        trigger.date,
        result,
    )
    return InjuryPredictionResponse(
        risk_level=result["risk_level"],
        risk_score=result["risk_score"],
        prediction_confidence=result["prediction_confidence"],
    )


@router.get("/status/ml")
def ml_status():
    """Expose model liveness and gate metadata for operational debugging."""
    return get_model_status()
