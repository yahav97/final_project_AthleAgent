"""ML selection gates and feature-engineering defaults.

Used by training, validation, the demo notebook, and backend/config.py defaults.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

# Selection gates — backend/config.py imports DEFAULT_MIN_* for Settings defaults.
DEFAULT_THRESHOLD: float = 0.18
DEFAULT_MIN_RECALL_HARD: float = 0.80
DEFAULT_MIN_AUC_FOR_LIVE: float = 0.68
DEFAULT_MAX_FPR_OPERATING: float = 0.55
DEFAULT_TARGET_RECALL: float = 0.80
DEFAULT_TARGET_PRECISION: float = 0.13
DEFAULT_TARGET_F1: float = 0.22

THRESHOLD = DEFAULT_THRESHOLD
MIN_RECALL_HARD = DEFAULT_MIN_RECALL_HARD
MIN_AUC_FOR_LIVE = DEFAULT_MIN_AUC_FOR_LIVE
MAX_FPR_OPERATING = DEFAULT_MAX_FPR_OPERATING
TARGET_RECALL = DEFAULT_TARGET_RECALL
TARGET_PRECISION = DEFAULT_TARGET_PRECISION
TARGET_F1 = DEFAULT_TARGET_F1

# Feature-engineering defaults — backend/config.py imports these.
DEFAULT_SLEEP_TARGET_HOURS: float = 8.0
DEFAULT_SLEEP_DEBT_SINGLE_DAY_PROXY_SCALE: float = 1.25

# Train-serve parity augmentation (training/serve_parity.py).
DEFAULT_COLD_START_AUGMENT_FRACTION: float = 0.25
DEFAULT_COLD_START_FIRST_N_DAYS: int = 7
DEFAULT_NUTRITION_MASK_FRACTION: float = 0.25


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


def policy_thresholds() -> dict[str, float]:
    return {
        "recall_hard_min": MIN_RECALL_HARD,
        "recall_target": TARGET_RECALL,
        "precision_min": TARGET_PRECISION,
        "f1_min": TARGET_F1,
        "fpr_max_operating": MAX_FPR_OPERATING,
        "fixed_comparison_threshold": THRESHOLD,
        "auc_min_for_live": MIN_AUC_FOR_LIVE,
    }


def evaluate_policy_gates(recall: float, precision: float, f1: float, fpr: float) -> dict[str, bool]:
    return {
        "recall_hard": recall >= MIN_RECALL_HARD,
        "fpr": fpr <= MAX_FPR_OPERATING,
        "precision": precision >= TARGET_PRECISION,
        "f1": f1 >= TARGET_F1,
    }


def policy_as_dict() -> dict[str, Any]:
    """Serialize policy for run manifests."""
    return {
        "recall_hard_min": MIN_RECALL_HARD,
        "recall_min": TARGET_RECALL,
        "fpr_max_operating": MAX_FPR_OPERATING,
        "precision_min": TARGET_PRECISION,
        "f1_min": TARGET_F1,
        "auc_min_for_live": MIN_AUC_FOR_LIVE,
        "fixed_comparison_threshold": THRESHOLD,
    }
