"""Unit tests for CV vs holdout stable model selection."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ML_ROOT = Path(__file__).resolve().parents[3] / "ML_model"
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

from training.constants import AthleteCvResult  # noqa: E402
from training.policy import pick_best_model, select_winner_with_cv_stability  # noqa: E402

pytestmark = pytest.mark.unit


def _cv_result(cv_order: list[str]) -> AthleteCvResult:
    summary = pd.DataFrame(
        {
            "Model": cv_order,
            "F1_mean": [0.5 - index * 0.05 for index in range(len(cv_order))],
            "Recall_mean": [0.8] * len(cv_order),
            "ROC_AUC_mean": [0.75] * len(cv_order),
        }
    )
    return AthleteCvResult(fold_details=pd.DataFrame(), summary=summary)


def _threshold_rows(model_name: str, *, recall: float, f1: float, tier_recall: float | None = None) -> list[dict]:
    recall_value = tier_recall if tier_recall is not None else recall
    return [
        {
            "Model": model_name,
            "Threshold": 0.18,
            "Recall": recall_value,
            "Precision": 0.2,
            "F1": f1,
            "FPR": 0.4,
        }
    ]


class TestCvHoldoutStableSelection:
    def test_agreement_when_cv_top_is_holdout_pure_winner(self):
        results_df = pd.DataFrame(
            [
                {"Model": "Alpha", "ROC-AUC": 0.8, "PR-AUC": 0.5, "BrierScore": 0.1, "LogLoss": 0.4},
                {"Model": "Beta", "ROC-AUC": 0.7, "PR-AUC": 0.4, "BrierScore": 0.12, "LogLoss": 0.5},
            ]
        )
        threshold_rows = _threshold_rows("Alpha", recall=0.85, f1=0.45) + _threshold_rows(
            "Beta", recall=0.7, f1=0.3
        )
        row, info = select_winner_with_cv_stability(
            _cv_result(["Alpha", "Beta"]),
            results_df,
            threshold_rows,
        )
        assert str(row["Model"]) == "Alpha"
        assert info["agreement"] is True
        assert info["selection_reason"] == "cv_and_holdout_agree"

    def test_prefers_cv_leader_when_holdout_pure_differs_but_cv_top_passes_gate(self):
        results_df = pd.DataFrame(
            [
                {"Model": "CvBest", "ROC-AUC": 0.79, "PR-AUC": 0.5, "BrierScore": 0.11, "LogLoss": 0.41},
                {"Model": "HoldoutBest", "ROC-AUC": 0.81, "PR-AUC": 0.52, "BrierScore": 0.1, "LogLoss": 0.39},
            ]
        )
        threshold_rows = _threshold_rows("CvBest", recall=0.82, f1=0.42) + _threshold_rows(
            "HoldoutBest", recall=0.84, f1=0.44
        )
        row, info = select_winner_with_cv_stability(
            _cv_result(["CvBest", "HoldoutBest"]),
            results_df,
            threshold_rows,
        )
        assert str(row["Model"]) == "CvBest"
        assert info["holdout_pure_winner"] == "HoldoutBest"
        assert info["agreement"] is False

    def test_matches_pure_holdout_picker_when_cv_not_available(self):
        results_df = pd.DataFrame(
            [{"Model": "Only", "ROC-AUC": 0.8, "PR-AUC": 0.5, "BrierScore": 0.1, "LogLoss": 0.4}]
        )
        threshold_rows = _threshold_rows("Only", recall=0.83, f1=0.4)
        pure = pick_best_model(results_df, threshold_rows)
        row, info = select_winner_with_cv_stability(
            _cv_result(["Only"]),
            results_df,
            threshold_rows,
        )
        assert str(row["Model"]) == str(pure["Model"])
