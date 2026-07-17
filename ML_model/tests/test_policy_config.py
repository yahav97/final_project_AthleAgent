"""Unit tests for ML training policy gates and shared constants."""

from __future__ import annotations

import pytest

from policy_config import (
    DEFAULT_MIN_AUC_FOR_LIVE,
    DEFAULT_MIN_RECALL_HARD,
    evaluate_policy_gates,
    get_policy,
    policy_as_dict,
    policy_thresholds,
)


class TestPolicyConstants:
    def test_recall_hard_gate_matches_backend_default(self):
        assert DEFAULT_MIN_RECALL_HARD == pytest.approx(0.80)

    def test_auc_gate_matches_backend_default(self):
        assert DEFAULT_MIN_AUC_FOR_LIVE == pytest.approx(0.68)

    def test_policy_thresholds_keys_are_complete(self):
        keys = set(policy_thresholds().keys())
        assert keys == {
            "recall_hard_min",
            "recall_target",
            "precision_min",
            "f1_min",
            "fpr_max_operating",
            "fixed_comparison_threshold",
            "auc_min_for_live",
        }


class TestEvaluatePolicyGates:
    @pytest.mark.parametrize(
        ("recall", "precision", "f1", "fpr", "expected_pass"),
        [
            (0.81, 0.15, 0.25, 0.50, True),
            (0.79, 0.15, 0.25, 0.50, False),  # recall below hard gate
            (0.81, 0.10, 0.25, 0.50, False),  # precision below target
            (0.81, 0.15, 0.15, 0.50, False),  # f1 below target
            (0.81, 0.15, 0.25, 0.60, False),  # fpr above operating max
        ],
    )
    def test_gate_boundaries(self, recall, precision, f1, fpr, expected_pass):
        gates = evaluate_policy_gates(recall, precision, f1, fpr)
        assert all(gates.values()) == expected_pass

    def test_recall_exactly_at_hard_gate_passes(self):
        policy = get_policy()
        gates = evaluate_policy_gates(
            policy.MIN_RECALL_HARD,
            policy.TARGET_PRECISION,
            policy.TARGET_F1,
            policy.MAX_FPR_OPERATING,
        )
        assert gates["recall_hard"] is True


class TestPolicySerialization:
    def test_policy_as_dict_round_trips_required_keys(self):
        data = policy_as_dict()
        assert data["recall_hard_min"] == pytest.approx(DEFAULT_MIN_RECALL_HARD)
        assert data["auc_min_for_live"] == pytest.approx(DEFAULT_MIN_AUC_FOR_LIVE)
        assert data["recall_target"] == pytest.approx(0.80)
        assert "fixed_comparison_threshold" in data

    def test_policy_thresholds_is_alias_of_policy_as_dict(self):
        assert policy_thresholds() == policy_as_dict()
        assert policy_thresholds is policy_as_dict
