"""Resolve and validate the promoted model bundle contract."""

from __future__ import annotations

from typing import Any, NamedTuple

from schemas.enums import BundleResolutionMode, ModelGateReason


class ResolvedModelBundle(NamedTuple):
    """Result of parsing the joblib artifact for live inference.

    Training ``threshold`` must be present (contract gate) but risk bands at serve
    time come from ``config.settings`` / ``risk_levels`` (Android UI alignment).
    """

    estimator: Any | None
    feature_columns: list[str] | None
    model_name: str
    gate_status: str


def _blocked_bundle(gate: ModelGateReason) -> ResolvedModelBundle:
    """Return a bundle that cannot serve predictions."""
    return ResolvedModelBundle(
        None,
        None,
        BundleResolutionMode.FALLBACK_DEMO.value,
        gate.value,
    )


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
        return _blocked_bundle(ModelGateReason.MODEL_NOT_LOADED)
    if not isinstance(loaded_model, dict):
        return _blocked_bundle(ModelGateReason.UNSUPPORTED_MODEL_FORMAT)

    estimator = loaded_model.get("estimator")
    feature_columns = loaded_model.get("feature_columns")
    threshold_raw = loaded_model.get("threshold")
    model_name = str(loaded_model.get("winner") or "live_model")

    if estimator is None:
        return _blocked_bundle(ModelGateReason.MISSING_ESTIMATOR)
    if not isinstance(feature_columns, list) or not feature_columns:
        return _blocked_bundle(ModelGateReason.MISSING_FEATURE_COLUMNS)
    if threshold_raw is None:
        return _blocked_bundle(ModelGateReason.INVALID_THRESHOLD)
    try:
        float(threshold_raw)
    except (TypeError, ValueError):
        return _blocked_bundle(ModelGateReason.INVALID_THRESHOLD)

    return ResolvedModelBundle(
        estimator,
        [str(column) for column in feature_columns],
        model_name,
        ModelGateReason.NONE.value,
    )
