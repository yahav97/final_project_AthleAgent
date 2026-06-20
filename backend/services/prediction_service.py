"""Backward-compatible import path for prediction services."""

from ml.model_loader import get_model, get_model_gate_reason
from services.history_service import (
    fetch_daily_firestore_snapshot,
    get_history_window_context,
    save_daily_prediction_result,
)
from services.prediction.bundle import resolve_model_bundle
from services.prediction.confidence import (
    apply_history_confidence_fallback as _apply_history_confidence_fallback,
    count_defaulted_critical_features as _count_defaulted_critical_features,
    history_score_from_confidence as _history_score_from_confidence,
    prediction_confidence_0_100 as _prediction_confidence_0_100,
)
from services.prediction.firestore_mapping import (
    field_from_docs as _field_from_docs,
    firestore_doc_heartrate_avg as _firestore_doc_heartrate_avg,
    injury_prediction_request_from_firestore_snapshot,
)
from services.prediction.service import (
    persist_prediction_result_or_raise,
    predict_injury_risk,
    predict_injury_risk_from_firestore,
    training_base_feature_dict_from_request,
)

__all__ = [
    "_apply_history_confidence_fallback",
    "_count_defaulted_critical_features",
    "_field_from_docs",
    "_firestore_doc_heartrate_avg",
    "_history_score_from_confidence",
    "_prediction_confidence_0_100",
    "fetch_daily_firestore_snapshot",
    "get_history_window_context",
    "get_model",
    "get_model_gate_reason",
    "injury_prediction_request_from_firestore_snapshot",
    "persist_prediction_result_or_raise",
    "predict_injury_risk",
    "predict_injury_risk_from_firestore",
    "resolve_model_bundle",
    "save_daily_prediction_result",
    "training_base_feature_dict_from_request",
]
