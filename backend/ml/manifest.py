"""Normalize run_manifest.json from legacy training runs to the current schema."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from services.ml_policy import ml_gate_defaults

LEGACY_BENCHMARK_PATH = "ML_model/benchmark_holdout.csv"
CURRENT_BENCHMARK_PATH = "ML_model/data/benchmark_holdout.csv"


def canonical_manifest_policy() -> dict[str, float]:
    """Policy block shape written by ``ML_model/training/pipeline.save_training_artifacts``."""
    gates = ml_gate_defaults()
    return {
        "recall_hard_min": gates["min_recall_hard"],
        "recall_target": gates["target_recall"],
        "precision_min": gates["target_precision"],
        "f1_min": gates["target_f1"],
        "fpr_max_operating": gates["max_fpr_operating"],
        "fixed_comparison_threshold": gates["fixed_comparison_threshold"],
        "auc_min_for_live": gates["min_auc_for_live"],
    }


def normalize_manifest_policy(policy: dict[str, Any] | None) -> dict[str, float]:
    """Migrate legacy policy keys (e.g. ``recall_min``) and fill missing gate fields."""
    merged = dict(canonical_manifest_policy())
    if isinstance(policy, dict):
        if "recall_target" not in policy and policy.get("recall_min") is not None:
            merged["recall_target"] = float(policy["recall_min"])
        for key in merged:
            if key in policy and policy[key] is not None:
                merged[key] = float(policy[key])
    return merged


def normalize_run_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """
    Return a copy of ``manifest`` aligned with the current artifact schema.

    Legacy runs may include:
    - ``policy.recall_min`` instead of ``recall_target``
    - ``benchmark_path`` at ``ML_model/benchmark_holdout.csv``
    - top-level ``athlete_cv_splits`` / ``risk_bins`` (now CSV-only or nested)
    """
    out = deepcopy(manifest)

    out["policy"] = normalize_manifest_policy(out.get("policy") if isinstance(out.get("policy"), dict) else None)

    benchmark_path = out.get("benchmark_path")
    if benchmark_path == LEGACY_BENCHMARK_PATH:
        out["benchmark_path"] = CURRENT_BENCHMARK_PATH

    protocol = out.get("selection_protocol")
    if not isinstance(protocol, dict):
        protocol = {}
    else:
        protocol = dict(protocol)

    legacy_cv_splits = out.pop("athlete_cv_splits", None)
    if protocol.get("athlete_cv_splits") is None and legacy_cv_splits is not None:
        protocol["athlete_cv_splits"] = legacy_cv_splits
    out["selection_protocol"] = protocol

    # Holdout bin stats live in risk_bins_summary.csv; drop duplicated JSON blob.
    out.pop("risk_bins", None)

    return out
