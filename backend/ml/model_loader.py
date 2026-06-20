"""Load and expose the sklearn estimator used by prediction routes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import joblib

from utils.logging import logger

_estimator: Optional[Any] = None
_model_gate_reason: str = "model_not_loaded"
_model_live: bool = False
_active_manifest: dict[str, Any] = {}
_active_promoted: dict[str, Any] = {}

MIN_RECALL_HARD = 0.80
MIN_AUC_FOR_LIVE = 0.68

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


def _validate_manifest_for_live(manifest: dict[str, Any], model_path: Path) -> tuple[bool, str]:
    """Validate manifest quality gates before allowing model to be live."""
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

    if not model_path.is_file():
        return False, "model_file_not_found"
    return True, "none"


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
        _model_gate_reason = "model_file_not_found"
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
                _model_gate_reason = "fallback_bundle_invalid"
                _model_live = False
                _active_manifest = {}
                return None
            _estimator = bundle
            _model_gate_reason = "none"
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
        _model_gate_reason = "manifest_not_found"
        _model_live = False
        _active_manifest = {}
        return None

    try:
        with manifest_candidate.open("r", encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Manifest read failed at %s: %s", manifest_candidate, exc)
        _estimator = None
        _model_gate_reason = "manifest_corrupted"
        _model_live = False
        _active_manifest = {}
        return None

    valid, reason = _validate_manifest_for_live(manifest, path)
    if not valid:
        logger.warning("Model gate rejected load: %s", reason)
        _estimator = None
        _model_gate_reason = reason
        _model_live = False
        _active_manifest = manifest
        return None

    _estimator = joblib.load(path)
    _model_gate_reason = "none"
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
        try:
            auc_value = float(winner_metrics.get("ROC-AUC"))
        except (TypeError, ValueError):
            auc_value = None
        try:
            recall_value = float(winner_metrics.get("Recall@Threshold"))
        except (TypeError, ValueError):
            recall_value = None
    degraded_auc_threshold = MIN_AUC_FOR_LIVE + 0.02
    degraded_rc = bool(_model_live and auc_value is not None and auc_value < degraded_auc_threshold)
    run_id = _active_manifest.get("run_id") if isinstance(_active_manifest, dict) else None
    if not run_id and isinstance(_active_promoted, dict):
        run_id = _active_promoted.get("run_id")
    return {
        "status": "Live" if _model_live else "Blocked",
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
