"""Injury risk prediction HTTP routes."""

from fastapi import APIRouter, HTTPException
import pandas as pd

from config import settings
from ml.model_loader import get_model
from schemas.inference import (
    AthleteData,
    InjuryPredictionRequest,
    InjuryPredictionResponse,
    SimpleData,
)
from services.prediction_service import predict_injury_risk
from utils.logging import logger

router = APIRouter(tags=["Prediction"])


@router.post("/test_predict")
def test_predict_injury(data: SimpleData):
    return {
        "user_id": data.user_id,
        "risk_percentage": 72.5,
        "risk_level": "High",
        "message": "This is a mock response for Android UI testing",
    }


@router.post("/demo_predict")
def demo_predict_injury(data: AthleteData):
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
    """Production contract: Firestore-shaped daily payload in, risk assessment out."""
    try:
        result = predict_injury_risk(payload)
    except Exception as exc:
        logger.exception("predict_route_fallback_exception userId=%s err=%s", payload.userId, exc)
        sleep_hours = (payload.sleepMinutes or 0) / 60.0
        soreness = float(payload.muscleSoreness or 2)
        stress = float(payload.stressLevel or 40)
        score = 10.0
        if sleep_hours < 5.0:
            score += 30.0
        elif sleep_hours < 7.0:
            score += 15.0
        score += soreness * 7.0
        score += stress * 0.25
        risk_score = min(score / 100.0, 1.0)
        risk_level = "High" if risk_score > 0.6 else "Medium" if risk_score > 0.3 else "Low"
        result = {
            "risk_level": risk_level,
            "risk_score": round(risk_score, 4),
            "recommendation": "Server fallback response returned while model service is unavailable.",
            "data_quality_score": 0.0,
            "data_quality_status": "Poor",
            "meta": {
                "model_version": "fallback_demo",
                "fallback_reason": "predict_exception",
            },
        }
    return InjuryPredictionResponse(**result)


@router.post("/predict/sklearn")
def predict_injury_sklearn(data: AthleteData):
    """Legacy sklearn pipeline using engineered feature row (AthleteData)."""
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
