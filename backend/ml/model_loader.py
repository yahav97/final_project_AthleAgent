"""Load and expose the sklearn estimator used by prediction routes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import joblib

from config import settings
from schemas.enums import ModelGateReason, ModelLiveStatus
from utils.logging import logger

_estimator: Optional[Any] = None
_model_gate_reason: str = ModelGateReason.MODEL_NOT_LOADED.value
_model_live: bool = False
_active_manifest: dict[str, Any] = {}
_active_promoted: dict[str, Any] = {}

PathLike = Path | str


def _as_path(path: PathLike) -> Path:
    """Normalize str or Path to a Path."""
    return path if isinstance(path, Path) else Path(path)


def _project_root() -> Path:
    """Resolve project root path from backend/ml module location."""
    return Path(__file__).resolve().parents[2]


def _fallback_model_path() -> Path:
    """Bundled safety-net model shipped with the backend."""
    return Path(__file__).resolve().parents[1] / "injury_model.pkl"


def _resolve_under_project_root(path: PathLike) -> Path:
    """Resolve project-relative paths against the repo root; leave absolute paths unchanged."""
    candidate = _as_path(path)
    if candidate.is_absolute():
        return candidate
    return _project_root() / candidate


def _manifest_path_from_model_path(model_path: Path) -> Path:
    """Return manifest path candidate relative to model path/project layout."""
    model_dir_manifest = model_path.parent / "run_manifest.json"
    default_manifest = _project_root() / "ML_model" / "run_manifest.json"
    return model_dir_manifest if model_dir_manifest.is_file() else default_manifest


def _read_promoted_metadata() -> dict[str, Any]:
    """Load promotion pointer metadata from ML_model/artifacts/promoted.json."""
    promoted_path = _project_root() / "ML_model" / "artifacts" / "promoted.json"
    if not promoted_path.is_file():
        return {}
    try:
        with promoted_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _resolve_promoted_model_path() -> Path | None:
    """Read promoted.json and resolve its model_path relative to the project root."""
    promoted_path = _project_root() / "ML_model" / "artifacts" / "promoted.json"
    if not promoted_path.is_file():
        return None
    try:
        with promoted_path.open("r", encoding="utf-8") as f:
            promoted = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    model_path = promoted.get("model_path")
    if not isinstance(model_path, str) or not model_path.strip():
        return None
    return _resolve_under_project_root(model_path.strip())


def _resolve_effective_model_path(model_path: PathLike | None) -> Path:
    """Pick model path: explicit override → promoted.json → backend fallback."""
    if model_path is not None:
        return _resolve_under_project_root(model_path)

    promoted_path = _resolve_promoted_model_path()
    if promoted_path is not None:
        if promoted_path.is_file():
            return promoted_path
        logger.warning(
            "Promoted model not found at %s; falling back to %s.",
            promoted_path,
            _fallback_model_path(),
        )

    return _fallback_model_path()


def _validate_manifest_for_live(manifest: dict[str, Any], model_path: Path) -> tuple[bool, ModelGateReason]:
    """Validate manifest quality gates before allowing model to be live."""
    winner = str(manifest.get("winner") or "").strip()
    if not winner:
        return False, ModelGateReason.MANIFEST_MISSING_WINNER
    metrics = manifest.get("winner_metrics") or {}
    recall_raw = metrics.get("Recall@Threshold")
    if recall_raw is None:
        return False, ModelGateReason.MANIFEST_INVALID_RECALL
    try:
        recall = float(recall_raw)
    except (TypeError, ValueError):
        return False, ModelGateReason.MANIFEST_INVALID_RECALL
    auc_raw = metrics.get("ROC-AUC")
    if auc_raw is None:
        return False, ModelGateReason.MANIFEST_INVALID_AUC
    try:
        auc = float(auc_raw)
    except (TypeError, ValueError):
        return False, ModelGateReason.MANIFEST_INVALID_AUC
    if recall < settings.ML_MIN_RECALL_HARD:
        return False, ModelGateReason.MANIFEST_RECALL_BELOW_HARD_GATE
    if auc < settings.ML_MIN_AUC_FOR_LIVE:
        return False, ModelGateReason.MANIFEST_AUC_TOO_LOW

    policy = manifest.get("policy") or {}
    if "recall_hard_min" in policy:
        try:
            policy_hard_recall = float(policy["recall_hard_min"])
        except (TypeError, ValueError):
            return False, ModelGateReason.MANIFEST_INVALID_POLICY_RECALL_HARD_MIN
        if recall < policy_hard_recall:
            return False, ModelGateReason.MANIFEST_RECALL_BELOW_POLICY_HARD_MIN

    if not model_path.is_file():
        return False, ModelGateReason.MODEL_FILE_NOT_FOUND
    return True, ModelGateReason.NONE


def _load_bundle_without_manifest(path: Path) -> Optional[Any]:
    """Load fallback bundle when manifest/artifacts are unavailable."""
    try:
        bundle = joblib.load(path)
    except Exception as exc:
        logger.warning("Fallback model load failed at %s: %s", path, exc)
        return None
    if not isinstance(bundle, dict) or bundle.get("estimator") is None:
        logger.warning("Fallback model at %s is missing estimator bundle contract.", path)
        return None
    return bundle


def load_model(
    model_path: PathLike | None = None,
    manifest_path: PathLike | None = None,
) -> Optional[Any]:
    """Load and gate-validate the promoted model bundle.

    Resolution order:
    1. Explicit ``model_path`` override (project-relative or absolute).
    2. ``ML_model/artifacts/promoted.json`` → ``model_path`` (project-relative).
    3. ``backend/injury_model.pkl`` fallback when promoted pointer/file is missing.
    """
    global _estimator, _model_gate_reason, _model_live, _active_manifest, _active_promoted

    path = _resolve_effective_model_path(model_path)
    _active_promoted = _read_promoted_metadata()
    fallback_path = _fallback_model_path()
    using_fallback = path.resolve() == fallback_path.resolve()

    if not path.is_file():
        logger.warning("Model file not found at %s. Run ML_model/train_model.py first.", path)
        _estimator = None
        _model_gate_reason = ModelGateReason.MODEL_FILE_NOT_FOUND.value
        _model_live = False
        _active_manifest = {}
        return None

    manifest_candidate = (
        _resolve_under_project_root(manifest_path)
        if manifest_path is not None
        else _manifest_path_from_model_path(path)
    )

    if not manifest_candidate.is_file():
        if using_fallback:
            bundle = _load_bundle_without_manifest(path)
            if bundle is None:
                _estimator = None
                _model_gate_reason = ModelGateReason.FALLBACK_BUNDLE_INVALID.value
                _model_live = False
                _active_manifest = {}
                return None
            _estimator = bundle
            _model_gate_reason = ModelGateReason.NONE.value
            _model_live = True
            _active_manifest = {}
            logger.info(
                "Fallback model loaded from %s (no manifest gate).",
                path,
                extra={
                    "event": "model_loaded",
                    "model_path": str(path),
                    "run_id": _active_promoted.get("run_id"),
                    "promoted_at_utc": _active_promoted.get("promoted_at_utc"),
                },
            )
            return _estimator

        logger.warning("Manifest not found at %s; model will not be marked live.", manifest_candidate)
        _estimator = None
        _model_gate_reason = ModelGateReason.MANIFEST_NOT_FOUND.value
        _model_live = False
        _active_manifest = {}
        return None

    try:
        with manifest_candidate.open("r", encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Manifest read failed at %s: %s", manifest_candidate, exc)
        _estimator = None
        _model_gate_reason = ModelGateReason.MANIFEST_CORRUPTED.value
        _model_live = False
        _active_manifest = {}
        return None

    valid, reason = _validate_manifest_for_live(manifest, path)
    if not valid:
        logger.warning("Model gate rejected load: %s", reason)
        _estimator = None
        _model_gate_reason = reason.value
        _model_live = False
        _active_manifest = manifest
        return None

    _estimator = joblib.load(path)
    _model_gate_reason = ModelGateReason.NONE.value
    _model_live = True
    _active_manifest = manifest
    logger.info(
        "Model loaded successfully from %s (manifest=%s)",
        path,
        manifest_candidate,
        extra={
            "event": "model_loaded",
            "run_id": manifest.get("run_id"),
            "model_path": str(path),
            "manifest_path": str(manifest_candidate),
            "winner": manifest.get("winner"),
            "promoted_at_utc": _active_promoted.get("promoted_at_utc"),
        },
    )
    return _estimator


def get_model() -> Optional[Any]:
    """Return the cached estimator, or None if not loaded."""
    return _estimator


def get_model_gate_reason() -> str:
    """Return why model is not live (or 'none')."""
    return _model_gate_reason


def get_model_status() -> dict[str, Any]:
    """Return operational model status for internal monitoring endpoints."""
    policy = _active_manifest.get("policy") if isinstance(_active_manifest, dict) else {}
    winner = _active_manifest.get("winner") if isinstance(_active_manifest, dict) else None
    threshold = _active_manifest.get("threshold") if isinstance(_active_manifest, dict) else None
    winner_metrics = (
        _active_manifest.get("winner_metrics") if isinstance(_active_manifest, dict) else {}
    )
    if not isinstance(winner_metrics, dict):
        winner_metrics = {}
    auc_value = None
    recall_value = None
    if isinstance(_active_manifest, dict):
        auc_raw = winner_metrics.get("ROC-AUC")
        if auc_raw is not None:
            try:
                auc_value = float(auc_raw)
            except (TypeError, ValueError):
                auc_value = None
        recall_raw = winner_metrics.get("Recall@Threshold")
        if recall_raw is not None:
            try:
                recall_value = float(recall_raw)
            except (TypeError, ValueError):
                recall_value = None
    degraded_auc_threshold = settings.ML_MIN_AUC_FOR_LIVE + settings.ML_DEGRADED_AUC_OFFSET
    degraded_rc = bool(_model_live and auc_value is not None and auc_value < degraded_auc_threshold)
    run_id = _active_manifest.get("run_id") if isinstance(_active_manifest, dict) else None
    if not run_id and isinstance(_active_promoted, dict):
        run_id = _active_promoted.get("run_id")
    return {
        "status": ModelLiveStatus.LIVE.value if _model_live else ModelLiveStatus.BLOCKED.value,
        "gate_reason": _model_gate_reason,
        "winner": winner,
        "threshold": threshold,
        "policy": policy if isinstance(policy, dict) else {},
        "degraded_rc": degraded_rc,
        "run_id": run_id,
        "promoted_at_utc": _active_promoted.get("promoted_at_utc") if isinstance(_active_promoted, dict) else None,
        "manifest_path": _active_promoted.get("manifest_path") if isinstance(_active_promoted, dict) else None,
        "winner_metrics": {
            "Recall@Threshold": recall_value,
            "ROC-AUC": auc_value,
        },
    }
