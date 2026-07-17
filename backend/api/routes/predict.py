"""Injury risk prediction HTTP routes."""

from fastapi import APIRouter

from ml.model_loader import get_model_status
from schemas.inference import (
    DailyPredictionTriggerRequest,
    InjuryPredictionResponse,
)
from services.prediction.service import run_daily_prediction
from utils.request_context import user_id_var

router = APIRouter(tags=["Prediction"])


@router.post("/predict/daily", response_model=InjuryPredictionResponse)
def predict_injury_daily(trigger: DailyPredictionTriggerRequest) -> InjuryPredictionResponse:
    """
    Minimal trigger endpoint: frontend sends only userId/date; backend loads all
    relevant daily data directly from Firestore and runs production inference.

    API auth is not enforced here — Android clients do not send Bearer tokens.
    Demo deployments should bind to localhost only (see docker-compose.yml).
    """
    user_id_var.set(trigger.userId)
    result = run_daily_prediction(trigger.userId, trigger.date)
    return InjuryPredictionResponse(
        risk_level=result["risk_level"],
        risk_score=result["risk_score"],
        prediction_confidence=result["prediction_confidence"],
    )


@router.get("/status/ml")
def ml_status():
    """Expose model liveness and gate metadata for operational debugging."""
    return get_model_status()
