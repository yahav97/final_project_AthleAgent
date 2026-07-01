"""Single source of truth for ML model-selection policy gates.

Used by training (`train_model.py`), validation (`validate_metrics.py`),
the presentation notebook, and as defaults for backend serving gates.

Runtime overrides (notebook demo): call ``apply_policy_overrides(...)`` then
re-run training — a different candidate may win.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

# Canonical defaults — backend/config.py imports these for ML_MIN_* defaults.
DEFAULT_MIN_RECALL_HARD: float = 0.80
DEFAULT_MIN_AUC_FOR_LIVE: float = 0.68
DEFAULT_MAX_FPR_OPERATING: float = 0.55
DEFAULT_TARGET_RECALL: float = 0.80
DEFAULT_TARGET_PRECISION: float = 0.13
DEFAULT_TARGET_F1: float = 0.22
DEFAULT_THRESHOLD: float = 0.18

POLICY_FIELD_NAMES: tuple[str, ...] = (
    "THRESHOLD",
    "MIN_RECALL_HARD",
    "TARGET_RECALL",
    "TARGET_PRECISION",
    "TARGET_F1",
    "MAX_FPR_OPERATING",
    "MIN_AUC_FOR_LIVE",
)


@dataclass
class PolicyConfig:
    """Mutable policy gates for model selection and promotion checks."""

    THRESHOLD: float = DEFAULT_THRESHOLD
    MIN_RECALL_HARD: float = DEFAULT_MIN_RECALL_HARD
    TARGET_RECALL: float = DEFAULT_TARGET_RECALL
    TARGET_PRECISION: float = DEFAULT_TARGET_PRECISION
    TARGET_F1: float = DEFAULT_TARGET_F1
    MAX_FPR_OPERATING: float = DEFAULT_MAX_FPR_OPERATING
    MIN_AUC_FOR_LIVE: float = DEFAULT_MIN_AUC_FOR_LIVE


_active: PolicyConfig = PolicyConfig()


def get_default_policy() -> PolicyConfig:
    """Fresh copy of repository defaults (not the live mutable singleton)."""
    return PolicyConfig()


def get_policy() -> PolicyConfig:
    """Live policy used by training and validation."""
    return _active


def reset_policy() -> PolicyConfig:
    """Restore live policy to repository defaults."""
    global _active
    _active = PolicyConfig()
    return _active


def apply_policy_overrides(**overrides: float | None) -> PolicyConfig:
    """Override live policy values (pass ``None`` to skip a key)."""
    valid = {f.name for f in fields(PolicyConfig)}
    for key, value in overrides.items():
        if value is None:
            continue
        if key not in valid:
            raise ValueError(f"Unknown policy key {key!r}. Valid: {sorted(valid)}")
        setattr(_active, key, float(value))
    return _active


def policy_thresholds() -> dict[str, float]:
    p = _active
    return {
        "recall_hard_min": p.MIN_RECALL_HARD,
        "recall_target": p.TARGET_RECALL,
        "precision_min": p.TARGET_PRECISION,
        "f1_min": p.TARGET_F1,
        "fpr_max_operating": p.MAX_FPR_OPERATING,
        "fixed_comparison_threshold": p.THRESHOLD,
        "auc_min_for_live": p.MIN_AUC_FOR_LIVE,
    }


def evaluate_policy_gates(recall: float, precision: float, f1: float, fpr: float) -> dict[str, bool]:
    p = _active
    return {
        "recall_hard": recall >= p.MIN_RECALL_HARD,
        "fpr": fpr <= p.MAX_FPR_OPERATING,
        "precision": precision >= p.TARGET_PRECISION,
        "f1": f1 >= p.TARGET_F1,
    }


def policy_as_dict() -> dict[str, Any]:
    """Serialize live policy (for manifests and debugging)."""
    p = _active
    return {
        "recall_hard_min": p.MIN_RECALL_HARD,
        "recall_min": p.TARGET_RECALL,
        "fpr_max_operating": p.MAX_FPR_OPERATING,
        "precision_min": p.TARGET_PRECISION,
        "f1_min": p.TARGET_F1,
        "auc_min_for_live": p.MIN_AUC_FOR_LIVE,
        "fixed_comparison_threshold": p.THRESHOLD,
    }


def format_policy_knobs_template() -> dict[str, float | None]:
    """Notebook helper: ``None`` = keep default; set a float to experiment live."""
    return {name: None for name in POLICY_FIELD_NAMES}
