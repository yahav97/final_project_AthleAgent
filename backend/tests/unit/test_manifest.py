"""Unit tests for run_manifest normalization."""

from __future__ import annotations

import pytest

from ml.manifest import (
    CURRENT_BENCHMARK_PATH,
    LEGACY_BENCHMARK_PATH,
    canonical_manifest_policy,
    normalize_run_manifest,
)

pytestmark = pytest.mark.unit


def test_normalize_legacy_policy_recall_min_to_recall_target():
    manifest = {
        "policy": {
            "recall_hard_min": 0.8,
            "recall_min": 0.79,
            "auc_min_for_live": 0.68,
        },
        "winner": "XGBoostCalibratedTuned",
    }
    out = normalize_run_manifest(manifest)
    assert "recall_min" not in out["policy"]
    assert out["policy"]["recall_target"] == pytest.approx(0.79)


def test_normalize_legacy_benchmark_path():
    manifest = {"benchmark_path": LEGACY_BENCHMARK_PATH}
    out = normalize_run_manifest(manifest)
    assert out["benchmark_path"] == CURRENT_BENCHMARK_PATH


def test_normalize_moves_top_level_cv_splits_into_protocol():
    manifest = {
        "athlete_cv_splits": 2,
        "selection_protocol": {"metrics_source": "fixed_holdout_evaluation"},
    }
    out = normalize_run_manifest(manifest)
    assert "athlete_cv_splits" not in out
    assert out["selection_protocol"]["athlete_cv_splits"] == 2


def test_normalize_drops_top_level_risk_bins():
    manifest = {"risk_bins": [{"bin": "green_0_20", "samples": 1}]}
    out = normalize_run_manifest(manifest)
    assert "risk_bins" not in out


def test_canonical_policy_matches_ml_policy_json():
    policy = canonical_manifest_policy()
    assert set(policy) == {
        "recall_hard_min",
        "recall_target",
        "precision_min",
        "f1_min",
        "fpr_max_operating",
        "fixed_comparison_threshold",
        "auc_min_for_live",
    }
