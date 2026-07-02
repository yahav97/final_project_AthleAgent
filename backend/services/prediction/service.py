"""Orchestration of preprocessing, features, and model.predict_proba."""

from __future__ import annotations

from typing import Any

from schemas.enums import ModelGateReason
from schemas.inference import InjuryPredictionRequest
from services.prediction.bundle import resolve_model_bundle
from services.prediction.confidence import (
    apply_history_confidence_fallback,
    count_defaulted_critical_features,
    prediction_confidence_0_100,
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


def predict_injury_risk(payload: InjuryPredictionRequest) -> dict[str, Any]:
    """
    Run preprocessing → feature row → sklearn ``predict_proba`` (injury positive class).

    If ``injury_model.pkl`` is not present on the server, returns a conservative demo
    response so local development and CI still behave predictably.

    Client is expected to avoid calling until required inputs exist; missing load is
    surfaced via ``load_signal`` in data quality (confidence only, not HTTP rejection).
    """
    import services.prediction_service as prediction_service_module

    frame = injury_request_to_model_dataframe(payload)
    frame, history_confidence = apply_history_confidence_fallback(frame, payload)
    quality = calculate_data_quality_score(payload)
    score = quality["score"]
    quality_score = float(score) if isinstance(score, (int, float)) else 0.0
    logger.info(
        "predict_data_quality userId=%s date=%s quality=%.3f sensitive_missing_fields=%s hard_missing=%s",
        payload.userId,
        payload.date,
        quality_score,
        quality.get("sensitive_missing", []),
        quality.get("hard_missing", []),
        extra={"event": "predict_data_quality"},
    )
    prediction_confidence = prediction_confidence_0_100(history_confidence, quality_score)
    defaulted_critical_count = count_defaulted_critical_features(frame)
    logger.info(
        "predict_confidence_summary userId=%s prediction_confidence=%.2f defaulted_critical=%d",
        payload.userId,
        prediction_confidence,
        defaulted_critical_count,
        extra={"event": "predict_confidence_summary"},
    )

    loaded_model = prediction_service_module.get_model()
    (
        model,
        bundle_feature_columns,
        _model_threshold,
        _medium_threshold,
        _model_version,
        model_status,
    ) = resolve_model_bundle(loaded_model)
    if model is None:
        gate_reason = prediction_service_module.get_model_gate_reason()
        blocked_reason = (
            model_status
            if model_status != ModelGateReason.MODEL_NOT_LOADED.value
            else gate_reason
        )
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

    model_contract = {"estimator": model, "feature_columns": bundle_feature_columns}
    features = validate_feature_vector_for_model(frame, model_contract)

    probability = float(model.predict_proba(features)[0, 1])
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
    - Nutrition: ``daily_nutrition/{D-1}`` + population defaults for missing fields.
    """
    import services.prediction_service as prediction_service_module

    snapshot = prediction_service_module.fetch_daily_firestore_snapshot(user_id, date_key)
    if not snapshot:
        raise DatabaseError("Firestore snapshot unavailable", code="firestore_snapshot_unavailable")

    payload = injury_prediction_request_from_firestore_snapshot(user_id, date_key, snapshot)
    return prediction_service_module.predict_injury_risk(payload)


def persist_prediction_result_or_raise(
    user_id: str,
    date_key: str,
    result: dict[str, Any],
) -> None:
    import services.prediction_service as prediction_service_module

    saved = prediction_service_module.save_daily_prediction_result(user_id, date_key, result)
    if not saved:
        raise DatabaseError("Prediction persist failed", code="prediction_persist_failed")
