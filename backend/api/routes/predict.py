"""Injury risk prediction HTTP routes."""

from fastapi import APIRouter, HTTPException
import pandas as pd

from config import settings
from ml.model_loader import get_model, get_model_status
from services.model_features import DEFAULT_FEATURE_VALUES
from schemas.inference import (
    AthleteData,
    DailyPredictionTriggerRequest,
    InjuryPredictionResponse,
    SimpleData,
)
from services.prediction_service import (
    persist_prediction_result_or_raise,
    predict_injury_risk_from_firestore,
    resolve_model_bundle,
)
from services.risk_levels import classify_risk_level
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
            detail="Legacy endpoint disabled. Use POST /predict/daily.",
        )
    loaded = get_model()
    estimator, bundle_cols, *_rest = resolve_model_bundle(loaded)
    if estimator is None or not bundle_cols:
        return {"error": "Model not loaded"}

    merged = dict(DEFAULT_FEATURE_VALUES)
    for key, val in data.model_dump().items():
        if val is not None:
            merged[key] = float(val)
    input_df = pd.DataFrame({col: [merged[col]] for col in bundle_cols})
    risk_probability = estimator.predict_proba(input_df)[0][1]

    return {
        "risk_percentage": round(risk_probability * 100, 1),
        "risk_level": classify_risk_level(
            risk_probability,
            high=settings.LEGACY_SKLEARN_HIGH_CUTOFF,
            medium=settings.LEGACY_SKLEARN_MEDIUM_CUTOFF,
        ),
    }


@router.get("/status/ml")
def ml_status():
    """Expose model liveness and gate metadata for operational debugging."""
    return get_model_status()
