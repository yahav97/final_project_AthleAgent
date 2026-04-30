"""Load and expose the sklearn estimator used by prediction routes."""

from __future__ import annotations

import json
import os
from typing import Any, Optional

import joblib

from utils.logging import logger

_estimator: Optional[Any] = None
_model_gate_reason: str = "model_not_loaded"

MIN_RECALL_HARD = 0.85
MIN_AUC_FOR_LIVE = 0.60


def _manifest_path_from_model_path(model_path: str) -> str:
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    default_manifest = os.path.join(project_root, "ML_model", "run_manifest.json")
    model_dir_manifest = os.path.join(os.path.dirname(model_path), "run_manifest.json")
    return model_dir_manifest if os.path.exists(model_dir_manifest) else default_manifest


def _validate_manifest_for_live(manifest: dict[str, Any], model_path: str) -> tuple[bool, str]:
    winner = str(manifest.get("winner") or "").strip()
    if not winner:
        return False, "manifest_missing_winner"
    metrics = manifest.get("winner_metrics") or {}
    try:
        recall = float(metrics.get("Recall@Threshold"))
    except (TypeError, ValueError):
        return False, "manifest_invalid_recall"
    try:
        auc = float(metrics.get("ROC-AUC"))
    except (TypeError, ValueError):
        return False, "manifest_invalid_auc"
    if recall < MIN_RECALL_HARD:
        return False, "manifest_recall_below_hard_gate"
    if auc < MIN_AUC_FOR_LIVE:
        return False, "manifest_auc_too_low"

    policy = manifest.get("policy") or {}
    if "recall_hard_min" in policy:
        try:
            policy_hard_recall = float(policy["recall_hard_min"])
        except (TypeError, ValueError):
            return False, "manifest_invalid_policy_recall_hard_min"
        if recall < policy_hard_recall:
            return False, "manifest_recall_below_policy_hard_min"

    if not os.path.exists(model_path):
        return False, "model_file_not_found"
    return True, "none"


def load_model(model_path: str | None = None, manifest_path: str | None = None) -> Optional[Any]:
    """Load joblib model from disk. Idempotent: replaces cached estimator."""
    global _estimator, _model_gate_reason
    path = model_path or os.path.join(os.path.dirname(os.path.dirname(__file__)), "injury_model.pkl")
    if not os.path.exists(path):
        logger.warning("Model file not found at %s. Run ML_model/train_model.py first.", path)
        _estimator = None
        _model_gate_reason = "model_file_not_found"
        return None

    manifest_candidate = manifest_path or _manifest_path_from_model_path(path)
    if not os.path.exists(manifest_candidate):
        logger.warning("Manifest not found at %s; model will not be marked live.", manifest_candidate)
        _estimator = None
        _model_gate_reason = "manifest_not_found"
        return None

    try:
        with open(manifest_candidate, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Manifest read failed at %s: %s", manifest_candidate, exc)
        _estimator = None
        _model_gate_reason = "manifest_corrupted"
        return None

    valid, reason = _validate_manifest_for_live(manifest, path)
    if not valid:
        logger.warning("Model gate rejected load: %s", reason)
        _estimator = None
        _model_gate_reason = reason
        return None

    _estimator = joblib.load(path)
    _model_gate_reason = "none"
    logger.info("Model loaded successfully from %s (manifest=%s)", path, manifest_candidate)
    return _estimator


def get_model() -> Optional[Any]:
    """Return the cached estimator, or None if not loaded."""
    return _estimator


def get_model_gate_reason() -> str:
    """Return why model is not live (or 'none')."""
    return _model_gate_reason
