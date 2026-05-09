"""Injury risk prediction HTTP routes."""

from fastapi import APIRouter, HTTPException
import pandas as pd

from config import settings
from ml.model_loader import get_model, get_model_status
from schemas.inference import (
    AthleteData,
    DailyPredictionTriggerRequest,
    InjuryPredictionRequest,
    InjuryPredictionResponse,
    SimpleData,
)
from services.prediction_service import (
    persist_prediction_result_or_raise,
    predict_injury_risk,
    predict_injury_risk_from_firestore,
)
from utils.logging import logger

router = APIRouter(tags=["Prediction"])


@router.post("/test_predict")
def test_predict_injury(data: SimpleData):
    """Return a fixed mock payload for UI/API smoke usage.

    Args:
        data: Minimal request containing a user identifier.

    Returns:
        dict: Stable mock inference payload.
    """
    return {
        "user_id": data.user_id,
        "risk_percentage": 72.5,
        "risk_level": "High",
        "message": "This is a mock response for Android UI testing",
    }


@router.post("/demo_predict")
def demo_predict_injury(data: AthleteData):
    """Run a lightweight heuristic score for legacy demo clients.

    Args:
        data: Legacy athlete feature payload.

    Returns:
        dict: Risk percentage and categorical risk level.
    """
    score = 10.0

    if data.sleep_hours < 5.0:
        score += 30.0
    elif data.sleep_hours < 7.0:
        score += 15.0

    score += data.muscle_soreness * 7.0
    score += data.stress_level * 0.25

    if data.daily_distance_km > 12.0:
        score += 15.0

    final_score = min(score, 100.0)

    return {
        "risk_percentage": round(final_score, 1),
        "risk_level": "High" if final_score > 60 else "Medium" if final_score > 40 else "Low",
    }


@router.post("/predict", response_model=InjuryPredictionResponse)
def predict_injury_production(payload: InjuryPredictionRequest) -> InjuryPredictionResponse:
    """Run production inference with strict no-fallback semantics.

    Args:
        payload: Firestore-shaped daily athlete signals.

    Returns:
        InjuryPredictionResponse: Model-based risk prediction response.

    Raises:
        HTTPException: 500 if model is blocked, input quality is insufficient, or
            prediction execution fails.
    """
    try:
        result = predict_injury_risk(payload)
        if payload.userId and payload.date:
            persist_prediction_result_or_raise(
                payload.userId,
                payload.date,
                result,
                source="backend_predict_payload",
            )
    except Exception as exc:
        logger.exception("predict_route_error userId=%s err=%s", payload.userId, exc)
        raise HTTPException(status_code=500, detail=f"Prediction unavailable: {exc}") from exc
    return InjuryPredictionResponse(**result)


@router.post("/predict/daily", response_model=InjuryPredictionResponse)
def predict_injury_daily(trigger: DailyPredictionTriggerRequest) -> InjuryPredictionResponse:
    """
    Minimal trigger endpoint: frontend sends only userId/date; backend loads all
    relevant daily data directly from Firestore and runs production inference.
    """
    try:
        result = predict_injury_risk_from_firestore(trigger.userId, trigger.date)
        persist_prediction_result_or_raise(
            trigger.userId,
            trigger.date,
            result,
            source="backend_predict_daily",
        )
    except Exception as exc:
        logger.exception("predict_daily_route_error userId=%s err=%s", trigger.userId, exc)
        raise HTTPException(status_code=500, detail=f"Prediction unavailable: {exc}") from exc
    return InjuryPredictionResponse(**result)


@router.post("/predict/sklearn")
def predict_injury_sklearn(data: AthleteData):
    """Run legacy sklearn endpoint guarded behind explicit feature flag.

    Args:
        data: Legacy engineered feature row.

    Returns:
        dict: Legacy risk percentage response.
    """
    if not settings.ENABLE_LEGACY_SKLEARN_ENDPOINT:
        raise HTTPException(
            status_code=410,
            detail="Legacy endpoint disabled. Use POST /predict production contract.",
        )
    model = get_model()
    if model is None:
        return {"error": "Model not loaded"}

    input_df = pd.DataFrame([data.model_dump()])
    risk_probability = model.predict_proba(input_df)[0][1]

    return {
        "risk_percentage": round(risk_probability * 100, 1),
        "risk_level": "High" if risk_probability > 0.6 else "Medium" if risk_probability > 0.3 else "Low",
    }


@router.get("/status/ml")
def ml_status():
    """Expose model liveness and gate metadata for operational debugging."""
    return get_model_status()
