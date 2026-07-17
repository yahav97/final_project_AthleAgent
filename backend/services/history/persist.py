"""Persist prediction outputs to Firestore daily_health."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services.history.firestore_io import get_firestore_client
from utils.logging import logger


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
        risk_score = float(result.get("risk_score") or 0.0)
        confidence = float(result.get("prediction_confidence") or 0.0)
        doc = {
            "finalRiskScore": round(risk_score * 100.0, 2),
            "riskLevel": result.get("risk_level"),
            "predictionConfidence": round(min(100.0, max(0.0, confidence)), 2),
            "predictionUpdatedAt": datetime.now(timezone.utc).isoformat(),
        }
        db.collection("users").document(user_id).collection("daily_health").document(date_key).set(
            doc,
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
