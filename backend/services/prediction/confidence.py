"""Historical feature enrichment and prediction confidence scoring."""

from __future__ import annotations

from typing import Any

from schemas.enums import HistoryConfidence
from schemas.inference import InjuryPredictionRequest
from services.model_features import DEFAULT_FEATURE_VALUES

ROLLING_FEATURE_COLUMNS: tuple[str, ...] = (
    "acute_load_7d",
    "chronic_load_21d",
    "acwr_ratio",
    "acwr_ratio_ma7",
    "sleep_hours_ma7",
    "sleep_debt_3d",
    "hrv_drop",
)


def apply_history_confidence_fallback(
    frame,
    payload: InjuryPredictionRequest,
) -> tuple[Any, HistoryConfidence]:
    """
    Enrich row with historical rolling features and return confidence label.

    - high/medium confidence: use computed rolling features from Firestore.
    - low confidence (new athlete, <7 days): prefer stable profile averages for rolling
      fields to avoid noisy short-window artifacts.
    """
    confidence = HistoryConfidence.LOW
    if not (payload.userId and payload.date):
        return frame, confidence

    import services.prediction_service as prediction_service_module

    context = prediction_service_module.get_history_window_context(
        payload.userId,
        payload.date,
        lookback_days=7,
        include_target_day=False,
    )
    confidence_raw = context.get("confidence") or HistoryConfidence.LOW.value
    try:
        confidence = HistoryConfidence(confidence_raw)
    except ValueError:
        confidence = HistoryConfidence.LOW
    features = context.get("features") or {}

    if confidence in (HistoryConfidence.HIGH, HistoryConfidence.MEDIUM) and features:
        for column, value in features.items():
            if column in frame.columns:
                frame.at[frame.index[0], column] = float(value)
        return frame, confidence

    for column in ROLLING_FEATURE_COLUMNS:
        if column in frame.columns:
            frame.at[frame.index[0], column] = float(DEFAULT_FEATURE_VALUES[column])
    return frame, confidence


def history_score_from_confidence(confidence: HistoryConfidence) -> float:
    if confidence == HistoryConfidence.HIGH:
        return 0.95
    if confidence == HistoryConfidence.MEDIUM:
        return 0.7
    return 0.45


def prediction_confidence_0_100(confidence: HistoryConfidence, quality_score: float) -> float:
    """Blend history-window confidence with same-day input completeness (0–1) → 0–100."""
    history_score = history_score_from_confidence(confidence)
    combined = 0.6 * history_score + 0.4 * float(quality_score)
    return round(min(100.0, max(0.0, combined * 100.0)), 2)


def count_defaulted_critical_features(frame) -> int:
    count = 0
    for column in ROLLING_FEATURE_COLUMNS:
        if column not in frame.columns:
            continue
        observed = float(frame[column].iloc[0])
        default = float(DEFAULT_FEATURE_VALUES[column])
        if abs(observed - default) < 1e-9:
            count += 1
    return count
