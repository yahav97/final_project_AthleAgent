"""Public facade for history Firestore access (re-exports split modules).

Prefer importing from the focused modules directly:
- ``firestore_io`` — batch/document reads
- ``inference_bundle`` — production prediction load
- ``history_window`` — rolling history + confidence
- ``persist`` — write prediction results
"""

from __future__ import annotations

from services.history.firestore_client import get_firestore_client
from services.history.firestore_io import (
    doc_to_dict,
    read_firestore_document,
    read_firestore_documents,
)
from services.history.history_window import (
    build_history_window_context,
    fetch_user_history,
    get_history_window_context,
    history_confidence_from_quality_days,
    history_date_window,
    history_rows_from_snapshots,
)
from services.history.inference_bundle import fetch_inference_firestore_bundle
from services.history.persist import save_daily_prediction_result

__all__ = [
    "build_history_window_context",
    "doc_to_dict",
    "fetch_inference_firestore_bundle",
    "fetch_user_history",
    "get_firestore_client",
    "get_history_window_context",
    "history_confidence_from_quality_days",
    "history_date_window",
    "history_rows_from_snapshots",
    "read_firestore_document",
    "read_firestore_documents",
    "save_daily_prediction_result",
]
