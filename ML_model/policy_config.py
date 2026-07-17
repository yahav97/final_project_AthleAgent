"""ML selection gates and feature-engineering defaults.

Single source of truth: ``backend/data/ml_policy.json`` (also used by ``backend/config.py``).
The demo notebook may override module-level constants after import.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

POLICY_PATH = (
    Path(__file__).resolve().parents[1] / "backend" / "data" / "ml_policy.json"
)


def _load_policy_file() -> dict[str, Any]:
    with POLICY_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid ML policy at {POLICY_PATH}")
    return data


def _gate_value(policy: dict[str, Any], key: str) -> float:
    gates = policy["ml_gates"]
    if not isinstance(gates, dict):
        raise ValueError("ml_policy.json: ml_gates must be an object")
    return float(gates[key])


def _feature_default(policy: dict[str, Any], key: str) -> float:
    defaults = policy["feature_defaults"]
    if not isinstance(defaults, dict):
        raise ValueError("ml_policy.json: feature_defaults must be an object")
    return float(defaults[key])


def _parity_value(policy: dict[str, Any], key: str) -> float | int:
    parity = policy["train_serve_parity"]
    if not isinstance(parity, dict):
        raise ValueError("ml_policy.json: train_serve_parity must be an object")
    value = parity[key]
    if key.endswith("_days"):
        return int(value)
    return float(value)


_policy = _load_policy_file()

DEFAULT_THRESHOLD: float = _gate_value(_policy, "fixed_comparison_threshold")
DEFAULT_MIN_RECALL_HARD: float = _gate_value(_policy, "min_recall_hard")
DEFAULT_MIN_AUC_FOR_LIVE: float = _gate_value(_policy, "min_auc_for_live")
DEFAULT_MAX_FPR_OPERATING: float = _gate_value(_policy, "max_fpr_operating")
DEFAULT_TARGET_RECALL: float = _gate_value(_policy, "target_recall")
DEFAULT_TARGET_PRECISION: float = _gate_value(_policy, "target_precision")
DEFAULT_TARGET_F1: float = _gate_value(_policy, "target_f1")

THRESHOLD = DEFAULT_THRESHOLD
MIN_RECALL_HARD = DEFAULT_MIN_RECALL_HARD
MIN_AUC_FOR_LIVE = DEFAULT_MIN_AUC_FOR_LIVE
MAX_FPR_OPERATING = DEFAULT_MAX_FPR_OPERATING
TARGET_RECALL = DEFAULT_TARGET_RECALL
TARGET_PRECISION = DEFAULT_TARGET_PRECISION
TARGET_F1 = DEFAULT_TARGET_F1

DEFAULT_SLEEP_TARGET_HOURS: float = _feature_default(_policy, "sleep_target_hours")

# Train-serve parity augmentation (training/serve_parity.py).
DEFAULT_COLD_START_AUGMENT_FRACTION: float = float(
    _parity_value(_policy, "cold_start_augment_fraction")
)
DEFAULT_COLD_START_FIRST_N_DAYS: int = int(_parity_value(_policy, "cold_start_first_n_days"))
DEFAULT_NUTRITION_MASK_FRACTION: float = float(
    _parity_value(_policy, "nutrition_mask_fraction")
)


def get_policy() -> SimpleNamespace:
    """Current gate values (notebook may edit module constants before training)."""
    return SimpleNamespace(
        THRESHOLD=THRESHOLD,
        MIN_RECALL_HARD=MIN_RECALL_HARD,
        TARGET_RECALL=TARGET_RECALL,
        TARGET_PRECISION=TARGET_PRECISION,
        TARGET_F1=TARGET_F1,
        MAX_FPR_OPERATING=MAX_FPR_OPERATING,
        MIN_AUC_FOR_LIVE=MIN_AUC_FOR_LIVE,
    )


def policy_as_dict() -> dict[str, Any]:
    """Serialize policy for manifests, notebooks, and gate displays."""
    return {
        "recall_hard_min": MIN_RECALL_HARD,
        "recall_target": TARGET_RECALL,
        "precision_min": TARGET_PRECISION,
        "f1_min": TARGET_F1,
        "fpr_max_operating": MAX_FPR_OPERATING,
        "fixed_comparison_threshold": THRESHOLD,
        "auc_min_for_live": MIN_AUC_FOR_LIVE,
    }


# Back-compat alias used by the demo notebook.
policy_thresholds = policy_as_dict


def evaluate_policy_gates(recall: float, precision: float, f1: float, fpr: float) -> dict[str, bool]:
    return {
        "recall_hard": recall >= MIN_RECALL_HARD,
        "fpr": fpr <= MAX_FPR_OPERATING,
        "precision": precision >= TARGET_PRECISION,
        "f1": f1 >= TARGET_F1,
    }
