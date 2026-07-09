"""Orchestration of preprocessing, features, and model.predict_proba."""

from __future__ import annotations

from typing import Any

from ml.model_loader import get_model, get_model_gate_reason
from schemas.enums import ModelGateReason
from schemas.inference import InjuryPredictionRequest
from services.history.repository import (
    fetch_inference_firestore_bundle,
    save_daily_prediction_result,
)
from services.nutrition_defaults import resolve_request_nutrition
from services.profile_defaults import resolve_request_age
from services.prediction.bundle import resolve_model_bundle
from services.prediction.confidence import (
    apply_history_confidence_fallback,
    compute_prediction_confidence_percent,
    count_defaulted_critical_features,
)
from services.prediction.firestore_mapping import injury_prediction_request_from_firestore_snapshot
from services.preprocessing import (
    calculate_data_quality_score,
    injury_request_to_model_dataframe,
    validate_feature_vector_for_model,
)
from services.risk_levels import classify_risk_level
from utils.exceptions import DatabaseError, MLModelError
from utils.logging import logger


def predict_injury_risk(
    payload: InjuryPredictionRequest,
    *,
    history_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Run preprocessing → feature row → sklearn ``predict_proba`` (injury positive class).

    Raises ``MLModelError`` when the promoted model bundle is not live.
    Missing or zero measurements lower ``prediction_confidence`` only (never HTTP rejection).
    """
    payload = resolve_request_nutrition(payload)
    payload = resolve_request_age(payload)
    frame = injury_request_to_model_dataframe(payload)
    frame, history_confidence = apply_history_confidence_fallback(
        frame,
        payload,
        history_context=history_context,
    )
    quality = calculate_data_quality_score(payload)
    quality_score = float(quality["score"])
    logger.info(
        "predict_data_quality userId=%s date=%s quality=%.3f weak_fields=%s",
        payload.userId,
        payload.date,
        quality_score,
        quality.get("weak_fields", []),
        extra={"event": "predict_data_quality"},
    )
    prediction_confidence = compute_prediction_confidence_percent(history_confidence, quality_score)
    defaulted_critical_count = count_defaulted_critical_features(frame)
    logger.info(
        "predict_confidence_summary userId=%s prediction_confidence=%.2f defaulted_critical=%d",
        payload.userId,
        prediction_confidence,
        defaulted_critical_count,
        extra={"event": "predict_confidence_summary"},
    )

    loaded_model = get_model()
    bundle = resolve_model_bundle(loaded_model)
    if bundle.estimator is None:
        blocked_reason = bundle.gate_status
        if blocked_reason == ModelGateReason.MODEL_NOT_LOADED.value:
            blocked_reason = get_model_gate_reason()
        logger.warning(
            "predict_blocked userId=%s reason=%s prediction_confidence=%.2f",
            payload.userId,
            blocked_reason,
            prediction_confidence,
            extra={"event": "predict_blocked"},
        )
        raise MLModelError(
            f"Model is not live: {blocked_reason}",
            code=f"model_not_live:{blocked_reason}",
        )

    model_contract = {"estimator": bundle.estimator, "feature_columns": bundle.feature_columns}
    features = validate_feature_vector_for_model(frame, model_contract)

    probability = float(bundle.estimator.predict_proba(features)[0, 1])
    return {
        "risk_level": classify_risk_level(probability),
        "risk_score": round(probability, 4),
        "prediction_confidence": prediction_confidence,
    }


def predict_injury_risk_from_firestore(user_id: str, date_key: str) -> dict[str, Any]:
    """
    Single-source serving path: load inputs from Firestore and run production inference.

    Merge policy (wake-up day ``D``):
    - Sleep: ``daily_health/{D}``.
    - Physical load: ``daily_health/{D-1}`` only.
    - Survey: ``daily_checkins/{D}``.
    - Nutrition: ``daily_nutrition/{D-1}`` + population defaults via ``resolve_request_nutrition``.
    """
    bundle = fetch_inference_firestore_bundle(user_id, date_key)
    snapshot = bundle.get("snapshot") or {}
    if not snapshot:
        raise DatabaseError("Firestore snapshot unavailable", code="firestore_snapshot_unavailable")

    payload = injury_prediction_request_from_firestore_snapshot(user_id, date_key, snapshot)
    return predict_injury_risk(
        payload,
        history_context=bundle.get("history_context"),
    )


def persist_prediction_result_or_raise(
    user_id: str,
    date_key: str,
    result: dict[str, Any],
) -> None:
    saved = save_daily_prediction_result(user_id, date_key, result)
    if not saved:
        raise DatabaseError("Prediction persist failed", code="prediction_persist_failed")
