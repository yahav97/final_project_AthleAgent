"""Validate first-iteration policy metrics from model_comparison.csv."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

TARGET_RECALL = 0.90
MIN_RECALL_THRESHOLD = 0.85
MIN_AUC_THRESHOLD = 0.64
TARGET_PRECISION = 0.30
TARGET_F1 = 0.45
THRESHOLD = 0.4


def _latest_artifacts_dir(script_dir: str) -> str | None:
    root = Path(script_dir) / "artifacts"
    if not root.exists():
        return None
    candidates = [p for p in root.iterdir() if p.is_dir()]
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.name, reverse=True)
    return str(candidates[0])


def main() -> int:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    artifacts_dir = _latest_artifacts_dir(script_dir) or script_dir
    comparison_path = os.path.join(artifacts_dir, "model_comparison.csv")
    if not os.path.exists(comparison_path):
        print("model_comparison.csv not found. Run train_model.py first.")
        return 1

    df = pd.read_csv(comparison_path)
    required_columns = {
        "Model",
        "Recall@Threshold",
        "Precision@Threshold",
        "F1@Threshold",
        "FPR@Threshold",
        "BrierScore",
        "ROC-AUC",
        "LogLoss",
    }
    missing = required_columns - set(df.columns)
    if missing:
        print(f"model_comparison.csv missing columns: {sorted(missing)}")
        return 1

    ranked = df.sort_values(
        by=[
            "Recall@Threshold",
            "FPR@Threshold",
            "F1@Threshold",
            "Precision@Threshold",
            "BrierScore",
            "ROC-AUC",
        ],
        ascending=[False, True, False, False, True, False],
    )
    top = ranked.iloc[0]
    print(f"Policy threshold: {THRESHOLD}")
    print(ranked.to_string(index=False))

    recall_value = float(top["Recall@Threshold"])
    recall_hard_gate_ok = recall_value >= MIN_RECALL_THRESHOLD
    recall_target_ok = recall_value >= TARGET_RECALL
    auc_ok = float(top["ROC-AUC"]) >= MIN_AUC_THRESHOLD
    precision_ok = float(top["Precision@Threshold"]) >= TARGET_PRECISION
    f1_ok = float(top["F1@Threshold"]) >= TARGET_F1
    if not recall_hard_gate_ok:
        print(
            f"\nREJECTED: {top['Model']} failed hard safety gate "
            f"(Recall={recall_value:.4f} < {MIN_RECALL_THRESHOLD})."
        )
        return 2

    if recall_target_ok and auc_ok and precision_ok and f1_ok:
        print(
            f"\nPASS: {top['Model']} meets targets "
            f"(Recall>={TARGET_RECALL}, AUC>={MIN_AUC_THRESHOLD}, Precision>={TARGET_PRECISION}, F1>={TARGET_F1}). "
            f"Hard gate: Recall>={MIN_RECALL_THRESHOLD}."
        )
        return 0

    print(
        f"\nWARN: Top model {top['Model']} does not meet all targets "
        f"(Recall>={TARGET_RECALL}, AUC>={MIN_AUC_THRESHOLD}, Precision>={TARGET_PRECISION}, F1>={TARGET_F1}) "
        f"but passes hard gate Recall>={MIN_RECALL_THRESHOLD}."
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
