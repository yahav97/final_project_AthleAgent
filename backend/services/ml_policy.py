"""Shared ML policy gates — loaded from ``backend/data/ml_policy.json``."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ML_POLICY_PATH = Path(__file__).resolve().parents[1] / "data" / "ml_policy.json"


@lru_cache(maxsize=1)
def load_ml_policy() -> dict[str, Any]:
    with ML_POLICY_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid ML policy at {ML_POLICY_PATH}")
    return data


def _require_mapping(policy: dict[str, Any], key: str) -> dict[str, Any]:
    value = policy[key]
    if not isinstance(value, dict):
        raise ValueError(f"ml_policy.json: {key} must be an object")
    return value


def ml_gate_defaults() -> dict[str, float]:
    """Gate thresholds used by training selection and backend live model loading."""
    gates = _require_mapping(load_ml_policy(), "ml_gates")
    return {
        "min_recall_hard": float(gates["min_recall_hard"]),
        "min_auc_for_live": float(gates["min_auc_for_live"]),
        "max_fpr_operating": float(gates["max_fpr_operating"]),
        "target_recall": float(gates["target_recall"]),
        "target_precision": float(gates["target_precision"]),
        "target_f1": float(gates["target_f1"]),
        "fixed_comparison_threshold": float(gates["fixed_comparison_threshold"]),
    }


def sleep_target_hours_default() -> float:
    defaults = _require_mapping(load_ml_policy(), "feature_defaults")
    return float(defaults["sleep_target_hours"])
