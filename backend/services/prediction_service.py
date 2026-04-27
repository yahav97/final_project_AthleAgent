"""Orchestration of preprocessing, features, and model.predict_proba."""

from __future__ import annotations

from typing import Any

from ml.model_loader import get_model
from schemas.inference import InjuryPredictionRequest
from services.history_service import get_history_window_context
from services.model_features import DEFAULT_FEATURE_VALUES
from services.preprocessing import injury_request_to_model_dataframe, validate_feature_vector_for_model


def _recommendation(probability: float, acwr: float) -> str:
    if probability >= 0.6:
        return "Reduce training load today; prioritize sleep and recovery."
    if probability >= 0.35 or acwr >= 1.35:
        return "Moderate risk: consider lighter session and monitor soreness and sleep."
    if acwr >= 1.2:
        return "ACWR elevated: keep volume stable and avoid sharp spikes this week."
    return "Maintain current load; continue monitoring sleep and subjective readiness."


def _apply_history_confidence_fallback(df, payload: InjuryPredictionRequest) -> tuple[Any, str]:
    """
    Enrich row with historical rolling features and return confidence label.

    - high/medium confidence: use computed rolling features from Firestore.
    - low confidence (new athlete, <7 days): prefer stable profile averages for rolling
      fields to avoid noisy short-window artifacts.
    """
    confidence = "low"
    if not (payload.userId and payload.date):
        return df, confidence

    context = get_history_window_context(payload.userId, payload.date, lookback_days=7)
    confidence = str(context.get("confidence") or "low")
    features = context.get("features") or {}

    if confidence in ("high", "medium") and features:
        for col, value in features.items():
            if col in df.columns:
                df.at[df.index[0], col] = float(value)
        return df, confidence

    # New/insufficient history: use conservative profile averages for rolling fields.
    for col in ("acute_load_7d", "chronic_load_21d", "acwr_ratio", "sleep_debt_3d", "hrv_drop"):
        if col in df.columns:
            df.at[df.index[0], col] = float(DEFAULT_FEATURE_VALUES[col])
    return df, confidence


def _append_confidence_note(recommendation: str, confidence: str) -> str:
    if confidence == "high":
        return recommendation + " Confidence: high (7-day history available)."
    if confidence == "medium":
        return recommendation + " Confidence: medium (partial history available)."
    return recommendation + " Confidence: low (insufficient history; using profile/default baselines)."


def _resolve_estimator_and_features(loaded_model: Any) -> tuple[Any | None, list[str] | None]:
    """
    Support both legacy raw estimators and the new model bundle format.

    Bundle format (saved by ML_model/train_model.py):
      {"estimator": <model>, "feature_columns": [...], ...}
    """
    if loaded_model is None:
        return None, None
    if isinstance(loaded_model, dict):
        estimator = loaded_model.get("estimator")
        feature_columns = loaded_model.get("feature_columns")
        if isinstance(feature_columns, list):
            feature_columns = [str(c) for c in feature_columns]
        else:
            feature_columns = None
        return estimator, feature_columns
    return loaded_model, None


def predict_injury_risk(payload: InjuryPredictionRequest) -> dict[str, Any]:
    """
    Run preprocessing → feature row → sklearn ``predict_proba`` (injury positive class).

    If ``injury_model.pkl`` is not present on the server, returns a conservative demo
    response so local development and CI still behave predictably.
    """
    df = injury_request_to_model_dataframe(payload)
    df, history_confidence = _apply_history_confidence_fallback(df, payload)
    acwr = float(df["acwr_ratio"].iloc[0])

    loaded_model = get_model()
    model, bundle_feature_columns = _resolve_estimator_and_features(loaded_model)
    if model is None:
        return {
            "risk_level": "Low",
            "risk_score": 0.12,
            "recommendation": "Model artifact not loaded; demo response only. Train/copy injury_model.pkl to backend/.",
        }

    # Saved estimators may have been trained after feature selection (subset of MODEL_FEATURE_COLUMNS).
    model_contract = {"estimator": model, "feature_columns": bundle_feature_columns}
    X = validate_feature_vector_for_model(df, model_contract)

    proba = float(model.predict_proba(X)[0, 1])
    risk_level = "High" if proba > 0.6 else "Medium" if proba > 0.3 else "Low"

    return {
        "risk_level": risk_level,
        "risk_score": round(proba, 4),
        "recommendation": _append_confidence_note(_recommendation(proba, acwr), history_confidence),
    }
