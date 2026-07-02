"""Backward-compatible import path for prediction services."""

from ml.model_loader import get_model, get_model_gate_reason
from services.history.repository import (
    fetch_daily_firestore_snapshot,
    get_history_window_context,
    save_daily_prediction_result,
)
from services.prediction.bundle import resolve_model_bundle
from services.prediction.firestore_mapping import injury_prediction_request_from_firestore_snapshot
from services.prediction.service import (
    persist_prediction_result_or_raise,
    predict_injury_risk,
    predict_injury_risk_from_firestore,
)

__all__ = [
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
]
