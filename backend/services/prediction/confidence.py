"""Historical feature enrichment and prediction confidence scoring."""

from __future__ import annotations

from typing import Any

import pandas as pd

from config import settings
from schemas.enums import HistoryConfidence
from schemas.inference import InjuryPredictionRequest
from services.history.history_window import get_history_window_context
from services.model_features import DEFAULT_FEATURE_VALUES

# Rolling features filled from Firestore history or population defaults when history is thin.
HISTORY_ROLLING_FEATURES: tuple[str, ...] = (
    "acute_load_7d",
    "acwr_ratio",
    "acwr_ratio_ma7",
    "sleep_hours_ma7",
    "sleep_debt_3d",
    "hrv_drop",
)


def parse_history_confidence(confidence: HistoryConfidence | str) -> HistoryConfidence:
    """Normalize API / Firestore confidence label to HistoryConfidence enum."""
    if isinstance(confidence, HistoryConfidence):
        return confidence
    try:
        return HistoryConfidence(confidence)
    except ValueError:
        return HistoryConfidence.LOW


def sync_load_recovery_imbalance(feature_frame: pd.DataFrame) -> None:
    """Recompute composite from final acwr_ratio and sleep_debt_3d (after history fallback)."""
    idx = feature_frame.index[0]
    acwr = float(feature_frame.at[idx, "acwr_ratio"])
    sleep_debt = float(feature_frame.at[idx, "sleep_debt_3d"])
    feature_frame.at[idx, "load_recovery_imbalance"] = acwr * sleep_debt


def apply_history_confidence_fallback(
    feature_frame: pd.DataFrame,
    payload: InjuryPredictionRequest,
    *,
    history_context: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, HistoryConfidence]:
    """
    Enrich row with historical rolling features and return confidence label.

    - high/medium confidence: use computed rolling features from Firestore.
    - low confidence (new athlete, <7 days): prefer stable profile averages for rolling
      fields to avoid noisy short-window artifacts.
    """
    confidence = HistoryConfidence.LOW
    if history_context is None:
        if not (payload.userId and payload.date):
            return feature_frame, confidence
        history_context = get_history_window_context(
            payload.userId,
            payload.date,
            lookback_days=settings.HISTORY_LOOKBACK_DAYS,
            include_target_day=False,
        )
    elif not (payload.userId and payload.date):
        return feature_frame, confidence

    confidence_raw = history_context.get("confidence") or HistoryConfidence.LOW.value
    confidence = parse_history_confidence(confidence_raw)
    features = history_context.get("features") or {}

    if confidence in (HistoryConfidence.HIGH, HistoryConfidence.MEDIUM) and features:
        for column, value in features.items():
            if column in feature_frame.columns:
                feature_frame.at[feature_frame.index[0], column] = float(value)
        sync_load_recovery_imbalance(feature_frame)
        return feature_frame, confidence

    for column in HISTORY_ROLLING_FEATURES:
        if column in feature_frame.columns:
            feature_frame.at[feature_frame.index[0], column] = float(DEFAULT_FEATURE_VALUES[column])
    sync_load_recovery_imbalance(feature_frame)
    return feature_frame, confidence


def history_score_from_confidence(confidence: HistoryConfidence | str) -> float:
    """Map high/medium/low history bands to the numeric weights in ``settings``."""
    level = parse_history_confidence(confidence)
    if level == HistoryConfidence.HIGH:
        return settings.CONFIDENCE_SCORE_HIGH
    if level == HistoryConfidence.MEDIUM:
        return settings.CONFIDENCE_SCORE_MEDIUM
    return settings.CONFIDENCE_SCORE_LOW


def compute_prediction_confidence_percent(
    confidence: HistoryConfidence | str,
    quality_score: float,
) -> float:
    """Blend history-window confidence with same-day input completeness → 0–100."""
    history_score = history_score_from_confidence(confidence)
    combined = (
        settings.CONFIDENCE_HISTORY_WEIGHT * history_score
        + settings.CONFIDENCE_QUALITY_WEIGHT * float(quality_score)
    )
    return round(min(100.0, max(0.0, combined * 100.0)), 2)


def count_defaulted_critical_features(feature_frame: pd.DataFrame) -> int:
    """How many rolling features still match population defaults (thin history signal)."""
    count = 0
    for column in HISTORY_ROLLING_FEATURES:
        if column not in feature_frame.columns:
            continue
        observed = float(feature_frame[column].iloc[0])
        default = float(DEFAULT_FEATURE_VALUES[column])
        if abs(observed - default) < 1e-9:
            count += 1
    return count
