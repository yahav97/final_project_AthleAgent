"""Resolve and validate the promoted model bundle contract."""

from __future__ import annotations

from typing import Any, NamedTuple

from schemas.enums import BundleResolutionMode, ModelGateReason


class ResolvedModelBundle(NamedTuple):
    """Result of parsing the joblib artifact for live inference."""

    estimator: Any | None
    feature_columns: list[str] | None
    injury_threshold: float | None
    medium_risk_threshold: float | None
    model_name: str
    gate_status: str


def resolve_model_bundle(loaded_model: Any) -> ResolvedModelBundle:
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
        return ResolvedModelBundle(
            None,
            None,
            None,
            None,
            BundleResolutionMode.FALLBACK_DEMO.value,
            ModelGateReason.MODEL_NOT_LOADED.value,
        )
    if not isinstance(loaded_model, dict):
        return ResolvedModelBundle(
            None,
            None,
            None,
            None,
            BundleResolutionMode.FALLBACK_DEMO.value,
            ModelGateReason.UNSUPPORTED_MODEL_FORMAT.value,
        )

    estimator = loaded_model.get("estimator")
    feature_columns = loaded_model.get("feature_columns")
    threshold_raw = loaded_model.get("threshold")
    medium_threshold_raw = loaded_model.get("medium_threshold")
    model_name = str(loaded_model.get("winner") or "live_model")

    if estimator is None:
        return ResolvedModelBundle(
            None,
            None,
            None,
            None,
            BundleResolutionMode.FALLBACK_DEMO.value,
            ModelGateReason.MISSING_ESTIMATOR.value,
        )
    if not isinstance(feature_columns, list) or not feature_columns:
        return ResolvedModelBundle(
            None,
            None,
            None,
            None,
            BundleResolutionMode.FALLBACK_DEMO.value,
            ModelGateReason.MISSING_FEATURE_COLUMNS.value,
        )
    if threshold_raw is None:
        return ResolvedModelBundle(
            None,
            None,
            None,
            None,
            BundleResolutionMode.FALLBACK_DEMO.value,
            ModelGateReason.INVALID_THRESHOLD.value,
        )
    try:
        injury_threshold = float(threshold_raw)
    except (TypeError, ValueError):
        return ResolvedModelBundle(
            None,
            None,
            None,
            None,
            BundleResolutionMode.FALLBACK_DEMO.value,
            ModelGateReason.INVALID_THRESHOLD.value,
        )
    try:
        medium_risk_threshold = (
            float(medium_threshold_raw)
            if medium_threshold_raw is not None
            else max(0.15, injury_threshold * 0.6)
        )
    except (TypeError, ValueError):
        return ResolvedModelBundle(
            None,
            None,
            None,
            None,
            BundleResolutionMode.FALLBACK_DEMO.value,
            ModelGateReason.INVALID_MEDIUM_THRESHOLD.value,
        )

    return ResolvedModelBundle(
        estimator,
        [str(column) for column in feature_columns],
        injury_threshold,
        medium_risk_threshold,
        model_name,
        ModelGateReason.NONE.value,
    )
