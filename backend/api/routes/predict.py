"""Injury risk prediction HTTP routes."""

from fastapi import APIRouter
import pandas as pd

from ml.model_loader import get_model
from schemas.inference import (
    AthleteData,
    InjuryPredictionRequest,
    InjuryPredictionResponse,
    SimpleData,
)
from services.prediction_service import predict_injury_risk

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
    result = predict_injury_risk(payload)
    return InjuryPredictionResponse(**result)


@router.post("/predict/sklearn")
def predict_injury_sklearn(data: AthleteData):
    """Legacy sklearn pipeline using engineered feature row (AthleteData)."""
    model = get_model()
    if model is None:
        return {"error": "Model not loaded"}

    input_df = pd.DataFrame([data.model_dump()])
    risk_probability = model.predict_proba(input_df)[0][1]

    return {
        "risk_percentage": round(risk_probability * 100, 1),
        "risk_level": "High" if risk_probability > 0.6 else "Medium" if risk_probability > 0.3 else "Low",
    }
