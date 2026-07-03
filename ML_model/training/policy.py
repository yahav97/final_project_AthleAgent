"""Threshold metrics, operating-point selection, and model winner policy."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score

from policy_config import evaluate_policy_gates, get_policy
from training.constants import THRESHOLDS_TO_EVAL

OPERATING_TIER_LABELS: dict[int, str] = {
    0: "All gates pass",
    1: "Recall + FPR OK (precision/F1 relaxed)",
    2: "Recall OK only",
    3: "Fallback — no recall floor met",
}


def evaluate_with_threshold(y_true: pd.Series, y_proba: np.ndarray, threshold: float) -> dict[str, float]:
    y_pred = (y_proba >= threshold).astype(int)
    negatives = int((y_true == 0).sum())
    false_positives = int(((y_pred == 1) & (y_true == 0)).sum())
    false_positive_rate = (false_positives / negatives) if negatives > 0 else 0.0
    return {
        "Recall@Threshold": recall_score(y_true, y_pred, zero_division=0),
        "Precision@Threshold": precision_score(y_true, y_pred, zero_division=0),
        "F1@Threshold": f1_score(y_true, y_pred, zero_division=0),
        "FPR@Threshold": false_positive_rate,
    }


def print_split_diagnostics(y: pd.Series, y_train: pd.Series, y_test: pd.Series) -> None:
    overall_rate = float(y.mean())
    train_rate = float(y_train.mean())
    test_rate = float(y_test.mean())
    print("\nData split diagnostics:")
    print(f"- total_rows: {len(y)}")
    print(f"- train_rows: {len(y_train)}")
    print(f"- test_rows: {len(y_test)}")
    print(f"- injury_rate_overall: {overall_rate:.4f}")
    print(f"- injury_rate_train:   {train_rate:.4f}")
    print(f"- injury_rate_test:    {test_rate:.4f}")


def threshold_sweep(y_true: pd.Series, y_proba: np.ndarray, model_name: str) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    for threshold in THRESHOLDS_TO_EVAL:
        metrics = evaluate_with_threshold(y_true, y_proba, threshold)
        rows.append(
            {
                "Model": model_name,
                "Threshold": float(threshold),
                "Recall": float(metrics["Recall@Threshold"]),
                "Precision": float(metrics["Precision@Threshold"]),
                "F1": float(metrics["F1@Threshold"]),
                "FPR": float(metrics["FPR@Threshold"]),
            }
        )
    return rows


def select_best_operating_points(
    threshold_rows: list[dict[str, float | str]],
    min_recall: float | None = None,
    min_precision: float | None = None,
) -> pd.DataFrame:
    policy = get_policy()
    if min_recall is None:
        min_recall = policy.TARGET_RECALL
    if min_precision is None:
        min_precision = policy.TARGET_PRECISION
    df = pd.DataFrame(threshold_rows)
    feasible = df[(df["Recall"] >= min_recall) & (df["Precision"] >= min_precision)]
    if feasible.empty:
        return (
            df.sort_values(by=["F1", "Precision", "Recall", "FPR"], ascending=[False, False, False, True])
            .groupby("Model")
            .head(1)
        )
    return (
        feasible.sort_values(by=["F1", "Precision", "Recall", "FPR"], ascending=[False, False, False, True])
        .groupby("Model")
        .head(1)
        .sort_values(by=["F1", "Precision", "Recall", "FPR"], ascending=[False, False, False, True])
    )


def _rank_balanced_operating_points(model_df: pd.DataFrame) -> pd.DataFrame:
    return model_df.sort_values(
        by=["F1", "Precision", "FPR", "Recall", "Threshold"],
        ascending=[False, False, True, False, True],
    )


def select_operating_threshold_for_model(
    threshold_rows: list[dict[str, float | str]],
    model_name: str,
) -> float:
    df = pd.DataFrame(threshold_rows)
    policy = get_policy()
    model_df = df[df["Model"] == model_name].copy()
    if model_df.empty:
        return policy.THRESHOLD

    feasible = model_df[
        (model_df["Recall"] >= policy.MIN_RECALL_HARD)
        & (model_df["FPR"] <= policy.MAX_FPR_OPERATING)
    ]
    if not feasible.empty:
        return float(_rank_balanced_operating_points(feasible).iloc[0]["Threshold"])

    recall_ok = model_df[model_df["Recall"] >= policy.MIN_RECALL_HARD]
    if not recall_ok.empty:
        return float(_rank_balanced_operating_points(recall_ok).iloc[0]["Threshold"])

    return float(_rank_balanced_operating_points(model_df).iloc[0]["Threshold"])


def _best_operating_row_for_model(
    threshold_rows: list[dict[str, float | str]],
    model_name: str,
) -> tuple[pd.Series, int] | None:
    df = pd.DataFrame(threshold_rows)
    policy = get_policy()
    model_df = df[df["Model"] == model_name].copy()
    if model_df.empty:
        return None
    target = model_df[
        (model_df["Recall"] >= policy.MIN_RECALL_HARD)
        & (model_df["FPR"] <= policy.MAX_FPR_OPERATING)
        & (model_df["Precision"] >= policy.TARGET_PRECISION)
        & (model_df["F1"] >= policy.TARGET_F1)
    ]
    if not target.empty:
        return (_rank_balanced_operating_points(target).iloc[0], 0)

    relaxed = model_df[
        (model_df["Recall"] >= policy.MIN_RECALL_HARD)
        & (model_df["FPR"] <= policy.MAX_FPR_OPERATING)
    ]
    if not relaxed.empty:
        return (_rank_balanced_operating_points(relaxed).iloc[0], 1)

    recall_ok = model_df[model_df["Recall"] >= policy.MIN_RECALL_HARD]
    if not recall_ok.empty:
        return (_rank_balanced_operating_points(recall_ok).iloc[0], 2)

    return (_rank_balanced_operating_points(model_df).iloc[0], 3)


def build_risk_bin_table(y_true: pd.Series, y_proba: np.ndarray) -> pd.DataFrame:
    bins = pd.cut(
        y_proba,
        bins=[0.0, 0.2, 0.5, 1.0],
        labels=["green_0_20", "yellow_20_50", "red_50_100"],
        include_lowest=True,
        right=True,
    )
    frame = pd.DataFrame({"bin": bins, "injury": y_true.astype(int)})
    grouped = frame.groupby("bin", observed=False)["injury"].agg(["count", "mean"]).reset_index()
    grouped = grouped.rename(columns={"count": "samples", "mean": "injury_rate"})
    grouped["injury_rate"] = grouped["injury_rate"].fillna(0.0)
    return grouped


def pick_best_model(results_df: pd.DataFrame, threshold_rows: list[dict[str, float | str]]) -> pd.Series:
    """Select winner by balanced operating-point policy across all trained candidates."""
    operating_candidates: list[dict[str, float | str]] = []
    for model_name in results_df["Model"].tolist():
        row = _best_operating_row_for_model(threshold_rows, str(model_name))
        if row is None:
            continue
        selected_row, tier = row
        operating_candidates.append(
            {
                "Model": str(model_name),
                "OperatingTier": int(tier),
                "OperatingThreshold": float(selected_row["Threshold"]),
                "OperatingRecall": float(selected_row["Recall"]),
                "OperatingPrecision": float(selected_row["Precision"]),
                "OperatingF1": float(selected_row["F1"]),
                "OperatingFPR": float(selected_row["FPR"]),
            }
        )
    if operating_candidates:
        op_df = pd.DataFrame(operating_candidates)
        merged = op_df.merge(
            results_df[["Model", "ROC-AUC", "PR-AUC", "BrierScore", "LogLoss"]],
            on="Model",
            how="left",
        )
        return merged.sort_values(
            by=[
                "OperatingTier",
                "OperatingF1",
                "OperatingPrecision",
                "OperatingFPR",
                "OperatingRecall",
                "ROC-AUC",
                "PR-AUC",
                "BrierScore",
            ],
            ascending=[True, False, False, True, False, False, True, True],
        ).iloc[0]
    return results_df.sort_values(
        by=["F1@Threshold", "Precision@Threshold", "Recall@Threshold", "FPR@Threshold", "ROC-AUC"],
        ascending=[False, False, False, True, False],
    ).iloc[0]


def build_fixed_threshold_gate_table(results_df: pd.DataFrame) -> pd.DataFrame:
    """Mark pass/fail at the fixed comparison threshold (default 0.18)."""
    policy = get_policy()
    rows: list[dict[str, float | str | bool]] = []
    for _, row in results_df.iterrows():
        recall = float(row["Recall@Threshold"])
        precision = float(row["Precision@Threshold"])
        f1 = float(row["F1@Threshold"])
        fpr = float(row["FPR@Threshold"])
        gates = evaluate_policy_gates(recall, precision, f1, fpr)
        rows.append(
            {
                "Model": row["Model"],
                "Threshold": policy.THRESHOLD,
                "Recall": recall,
                "Precision": precision,
                "F1": f1,
                "FPR": fpr,
                "ROC-AUC": float(row["ROC-AUC"]),
                "BrierScore": float(row["BrierScore"]),
                "pass_recall_hard": gates["recall_hard"],
                "pass_fpr": gates["fpr"],
                "pass_precision": gates["precision"],
                "pass_f1": gates["f1"],
                "pass_all_gates": all(gates.values()),
                "failed_gates": ", ".join(name for name, ok in gates.items() if not ok) or "—",
            }
        )
    out = pd.DataFrame(rows)
    return out.sort_values(
        by=["pass_all_gates", "F1", "Recall", "ROC-AUC"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)


def build_operating_points_table(
    results_df: pd.DataFrame,
    threshold_rows: list[dict[str, float | str]],
) -> pd.DataFrame:
    """Per-model operating point and tier from the tiered selection algorithm."""
    rows: list[dict[str, float | str | bool | int]] = []
    for model_name in results_df["Model"].tolist():
        picked = _best_operating_row_for_model(threshold_rows, str(model_name))
        if picked is None:
            continue
        op_row, tier = picked
        recall = float(op_row["Recall"])
        precision = float(op_row["Precision"])
        f1 = float(op_row["F1"])
        fpr = float(op_row["FPR"])
        gates = evaluate_policy_gates(recall, precision, f1, fpr)
        base = results_df.loc[results_df["Model"] == model_name].iloc[0]
        rows.append(
            {
                "Model": model_name,
                "Tier": int(tier),
                "Tier meaning": OPERATING_TIER_LABELS[int(tier)],
                "Threshold": float(op_row["Threshold"]),
                "Recall": recall,
                "Precision": precision,
                "F1": f1,
                "FPR": fpr,
                "ROC-AUC": float(base["ROC-AUC"]),
                "BrierScore": float(base["BrierScore"]),
                "pass_recall_hard": gates["recall_hard"],
                "pass_fpr": gates["fpr"],
                "pass_precision": gates["precision"],
                "pass_f1": gates["f1"],
                "pass_all_gates": all(gates.values()),
                "failed_gates": ", ".join(name for name, ok in gates.items() if not ok) or "—",
            }
        )
    ranked = pd.DataFrame(rows).sort_values(
        by=["Tier", "F1", "Precision", "FPR", "Recall", "ROC-AUC", "BrierScore"],
        ascending=[True, False, False, True, False, False, True],
    ).reset_index(drop=True)
    ranked.insert(0, "Rank", ranked.index + 1)
    return ranked


def add_selection_column(operating_table: pd.DataFrame, winner_name: str) -> pd.DataFrame:
    out = operating_table.copy()
    out["Selected"] = out["Model"] == winner_name
    return out
