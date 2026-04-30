"""Validate first-iteration policy metrics from model_comparison.csv."""

from __future__ import annotations

import os
import sys

import pandas as pd

TARGET_RECALL = 0.90
MIN_RECALL_THRESHOLD = 0.85
TARGET_PRECISION = 0.30
TARGET_F1 = 0.45
THRESHOLD = 0.4


def main() -> int:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    comparison_path = os.path.join(script_dir, "model_comparison.csv")
    if not os.path.exists(comparison_path):
        print("model_comparison.csv not found. Run train_model.py first.")
        return 1

    df = pd.read_csv(comparison_path)
    required_columns = {"Model", "Recall@Threshold", "Precision@Threshold", "F1@Threshold", "ROC-AUC", "LogLoss"}
    missing = required_columns - set(df.columns)
    if missing:
        print(f"model_comparison.csv missing columns: {sorted(missing)}")
        return 1

    ranked = df.sort_values(
        by=["Recall@Threshold", "F1@Threshold", "Precision@Threshold", "ROC-AUC"],
        ascending=False,
    )
    top = ranked.iloc[0]
    print(f"Policy threshold: {THRESHOLD}")
    print(ranked.to_string(index=False))

    recall_value = float(top["Recall@Threshold"])
    recall_hard_gate_ok = recall_value >= MIN_RECALL_THRESHOLD
    recall_target_ok = recall_value >= TARGET_RECALL
    precision_ok = float(top["Precision@Threshold"]) >= TARGET_PRECISION
    f1_ok = float(top["F1@Threshold"]) >= TARGET_F1
    if not recall_hard_gate_ok:
        print(
            f"\nREJECTED: {top['Model']} failed hard safety gate "
            f"(Recall={recall_value:.4f} < {MIN_RECALL_THRESHOLD})."
        )
        return 2

    if recall_target_ok and precision_ok and f1_ok:
        print(
            f"\nPASS: {top['Model']} meets targets "
            f"(Recall>={TARGET_RECALL}, Precision>={TARGET_PRECISION}, F1>={TARGET_F1}). "
            f"Hard gate: Recall>={MIN_RECALL_THRESHOLD}."
        )
        return 0

    print(
        f"\nWARN: Top model {top['Model']} does not meet all targets "
        f"(Recall>={TARGET_RECALL}, Precision>={TARGET_PRECISION}, F1>={TARGET_F1}) "
        f"but passes hard gate Recall>={MIN_RECALL_THRESHOLD}."
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
