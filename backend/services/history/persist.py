"""Persist prediction outputs to Firestore daily_health."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from services.history.firestore_io import get_firestore_client, read_firestore_document
from utils.logging import logger

PREDICTION_CACHE_FIELDS: tuple[str, ...] = (
    "finalRiskScore",
    "riskLevel",
    "predictionConfidence",
)
PREDICTION_PERSIST_MAX_ATTEMPTS = 3
PREDICTION_PERSIST_RETRY_DELAY_SEC = 0.15


def _prediction_doc_from_result(result: dict[str, Any]) -> dict[str, Any]:
    risk_score = float(result.get("risk_score") or 0.0)
    confidence = float(result.get("prediction_confidence") or 0.0)
    return {
        "finalRiskScore": round(risk_score * 100.0, 2),
        "riskLevel": result.get("risk_level"),
        "predictionConfidence": round(min(100.0, max(0.0, confidence)), 2),
        "predictionUpdatedAt": datetime.now(timezone.utc).isoformat(),
    }


def load_cached_daily_prediction(user_id: str, date_key: str) -> dict[str, Any] | None:
    """
    Return a previously persisted prediction for ``user_id`` / ``date_key``.

    Used for idempotent POST /predict/daily — safe client retries without re-inference.
    """
    db = get_firestore_client()
    if db is None:
        return None
    try:
        doc_ref = (
            db.collection("users")
            .document(user_id)
            .collection("daily_health")
            .document(date_key)
        )
        snapshot = read_firestore_document(doc_ref, field_paths=PREDICTION_CACHE_FIELDS)
        data = snapshot.to_dict() if getattr(snapshot, "exists", False) else None
        if not data:
            return None

        risk_level = data.get("riskLevel")
        if risk_level not in ("Low", "Medium", "High"):
            return None

        final_score_raw = data.get("finalRiskScore")
        confidence_raw = data.get("predictionConfidence")
        if final_score_raw is None or confidence_raw is None:
            return None

        return {
            "risk_level": risk_level,
            "risk_score": round(float(final_score_raw) / 100.0, 4),
            "prediction_confidence": float(confidence_raw),
        }
    except Exception as exc:
        logger.warning(
            "load_cached_daily_prediction failed for user_id=%s date=%s: %s",
            user_id,
            date_key,
            exc,
            exc_info=True,
        )
        return None


def save_daily_prediction_result(
    user_id: str,
    date_key: str,
    result: dict[str, Any],
) -> bool:
    """Persist prediction output under users/{uid}/daily_health/{date} using merge."""
    db = get_firestore_client()
    if db is None:
        return False
    try:
        db.collection("users").document(user_id).collection("daily_health").document(date_key).set(
            _prediction_doc_from_result(result),
            merge=True,
        )
        return True
    except Exception as exc:
        logger.warning(
            "save_daily_prediction_result failed for user_id=%s date=%s: %s",
            user_id,
            date_key,
            exc,
            exc_info=True,
        )
        return False


def save_daily_prediction_result_with_retries(
    user_id: str,
    date_key: str,
    result: dict[str, Any],
    *,
    max_attempts: int = PREDICTION_PERSIST_MAX_ATTEMPTS,
    retry_delay_sec: float = PREDICTION_PERSIST_RETRY_DELAY_SEC,
) -> bool:
    """Best-effort Firestore write with short retries for transient failures."""
    attempts = max(1, int(max_attempts))
    for attempt in range(1, attempts + 1):
        if save_daily_prediction_result(user_id, date_key, result):
            if attempt > 1:
                logger.info(
                    "prediction_persist_succeeded_after_retry userId=%s date=%s attempt=%d",
                    user_id,
                    date_key,
                    attempt,
                    extra={"event": "prediction_persist_retry_success"},
                )
            return True
        if attempt < attempts and retry_delay_sec > 0:
            time.sleep(retry_delay_sec)
    return False

