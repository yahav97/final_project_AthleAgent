"""Orchestration of preprocessing, features, and model.predict_proba."""

from __future__ import annotations

from typing import Any

from ml.model_loader import get_model
from schemas.inference import InjuryPredictionRequest
from services.history_service import get_history_window_context
from services.model_features import DEFAULT_FEATURE_VALUES
from services.preprocessing import (
    calculate_data_quality_score,
    injury_request_to_model_dataframe,
    validate_feature_vector_for_model,
)
from utils.logging import logger


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


def _history_score_from_confidence(confidence: str) -> float:
    if confidence == "high":
        return 0.95
    if confidence == "medium":
        return 0.7
    return 0.45


def _combined_confidence(history_confidence: str, quality_score: float) -> str:
    score = 0.6 * _history_score_from_confidence(history_confidence) + 0.4 * quality_score
    if score >= 0.78:
        return "high"
    if score >= 0.52:
        return "medium"
    return "low"


def _quality_status(quality_score: float) -> str:
    if quality_score >= 0.9:
        return "Excellent"
    if quality_score >= 0.7:
        return "Good"
    if quality_score >= 0.45:
        return "Fair"
    return "Poor"


def _resolve_model_bundle(loaded_model: Any) -> tuple[Any | None, list[str] | None, float | None, str, str]:
    """
    Enforce a single model contract for serving.

    Required bundle format (saved by ML_model/train_model.py):
      {
        "estimator": <model>,
        "feature_columns": [...],
        "threshold": <float>,
        "winner": <str>
      }
    """
    if loaded_model is None:
        return None, None, None, "fallback_demo", "model_not_loaded"
    if not isinstance(loaded_model, dict):
        return None, None, None, "fallback_demo", "unsupported_model_format"

    estimator = loaded_model.get("estimator")
    feature_columns = loaded_model.get("feature_columns")
    threshold_raw = loaded_model.get("threshold")
    winner = str(loaded_model.get("winner") or "live_model")

    if estimator is None:
        return None, None, None, "fallback_demo", "missing_estimator"
    if not isinstance(feature_columns, list) or not feature_columns:
        return None, None, None, "fallback_demo", "missing_feature_columns"
    try:
        threshold = float(threshold_raw)
    except (TypeError, ValueError):
        return None, None, None, "fallback_demo", "invalid_threshold"

    return estimator, [str(c) for c in feature_columns], threshold, winner, "none"


def predict_injury_risk(payload: InjuryPredictionRequest) -> dict[str, Any]:
    """
    Run preprocessing → feature row → sklearn ``predict_proba`` (injury positive class).

    If ``injury_model.pkl`` is not present on the server, returns a conservative demo
    response so local development and CI still behave predictably.
    """
    df = injury_request_to_model_dataframe(payload)
    df, history_confidence = _apply_history_confidence_fallback(df, payload)
    quality = calculate_data_quality_score(payload)
    quality_score = float(quality["score"])
    quality_status = _quality_status(quality_score)
    logger.info(
        "predict_data_quality userId=%s date=%s quality=%.3f sensitive_missing_fields=%s hard_missing=%s",
        payload.userId,
        payload.date,
        quality_score,
        quality.get("sensitive_missing", []),
        quality.get("hard_missing", []),
    )
    final_confidence = _combined_confidence(history_confidence, quality_score)

    if bool(quality["has_hard_blocker"]) or quality_score < 0.35:
        return {
            "risk_level": "Low",
            "risk_score": 0.08,
            "recommendation": _append_confidence_note(
                "Insufficient data for accurate prediction. Conservative low-risk fallback returned.",
                final_confidence,
            ),
            "data_quality_score": round(quality_score, 4),
            "data_quality_status": quality_status,
            "meta": {
                "model_version": "fallback_demo",
                "fallback_reason": "insufficient_input_quality",
            },
        }
    acwr = float(df["acwr_ratio"].iloc[0])

    loaded_model = get_model()
    model, bundle_feature_columns, model_threshold, model_version, model_status = _resolve_model_bundle(
        loaded_model
    )
    if model is None:
        return {
            "risk_level": "Low",
            "risk_score": 0.12,
            "recommendation": "Model bundle is unavailable or invalid; conservative fallback returned.",
            "data_quality_score": round(quality_score, 4),
            "data_quality_status": quality_status,
            "meta": {
                "model_version": model_version,
                "fallback_reason": model_status,
            },
        }

    # Saved estimators may have been trained after feature selection (subset of MODEL_FEATURE_COLUMNS).
    model_contract = {"estimator": model, "feature_columns": bundle_feature_columns}
    X = validate_feature_vector_for_model(df, model_contract)

    proba = float(model.predict_proba(X)[0, 1])
    # Single source of truth: operating threshold comes from the saved model bundle.
    high_cutoff = float(model_threshold)
    medium_cutoff = max(0.15, high_cutoff * 0.6)
    risk_level = "High" if proba >= high_cutoff else "Medium" if proba >= medium_cutoff else "Low"

    return {
        "risk_level": risk_level,
        "risk_score": round(proba, 4),
        "recommendation": _append_confidence_note(_recommendation(proba, acwr), final_confidence),
        "data_quality_score": round(quality_score, 4),
        "data_quality_status": quality_status,
        "meta": {
            "model_version": model_version,
            "fallback_reason": "none",
        },
    }
