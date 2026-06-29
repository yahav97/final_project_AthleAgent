"""Train injury model with balanced precision–recall policy for production UX."""

from __future__ import annotations

import io
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    log_loss,
    precision_recall_curve,
    auc,
    precision_score,
    recall_score,
    roc_auc_score,
)

from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from xgboost import XGBClassifier

THRESHOLD = 0.18
MIN_RECALL_HARD = 0.80
TARGET_RECALL = 0.80
TARGET_PRECISION = 0.13
TARGET_F1 = 0.22
MAX_FPR_OPERATING = 0.55
RANDOM_STATE = 42
THRESHOLDS_TO_EVAL = sorted(
    {
        round(x, 2)
        for x in list(np.arange(0.10, 0.22, 0.01)) + list(np.arange(0.22, 0.62, 0.02))
    }
)

# Training label column (injury on row date D — not a model feature).
LABEL_COLUMN = "injury_today"
LEGACY_LABEL_COLUMN = "injury_tomorrow"


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
    min_recall: float = TARGET_RECALL,
    min_precision: float = TARGET_PRECISION,
) -> pd.DataFrame:
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
    """Prefer higher F1/Precision while keeping recall above the hard floor and FPR bounded."""
    return model_df.sort_values(
        by=["F1", "Precision", "FPR", "Recall", "Threshold"],
        ascending=[False, False, True, False, True],
    )


def select_operating_threshold_for_model(
    threshold_rows: list[dict[str, float | str]],
    model_name: str,
) -> float:
    df = pd.DataFrame(threshold_rows)
    model_df = df[df["Model"] == model_name].copy()
    if model_df.empty:
        return THRESHOLD

    feasible = model_df[
        (model_df["Recall"] >= MIN_RECALL_HARD) & (model_df["FPR"] <= MAX_FPR_OPERATING)
    ]
    if not feasible.empty:
        return float(_rank_balanced_operating_points(feasible).iloc[0]["Threshold"])

    recall_ok = model_df[model_df["Recall"] >= MIN_RECALL_HARD]
    if not recall_ok.empty:
        return float(_rank_balanced_operating_points(recall_ok).iloc[0]["Threshold"])

    return float(_rank_balanced_operating_points(model_df).iloc[0]["Threshold"])


def _best_operating_row_for_model(
    threshold_rows: list[dict[str, float | str]],
    model_name: str,
) -> tuple[pd.Series, int] | None:
    df = pd.DataFrame(threshold_rows)
    model_df = df[df["Model"] == model_name].copy()
    if model_df.empty:
        return None
    target = model_df[
        (model_df["Recall"] >= MIN_RECALL_HARD)
        & (model_df["FPR"] <= MAX_FPR_OPERATING)
        & (model_df["Precision"] >= TARGET_PRECISION)
        & (model_df["F1"] >= TARGET_F1)
    ]
    if not target.empty:
        return (_rank_balanced_operating_points(target).iloc[0], 0)

    relaxed = model_df[
        (model_df["Recall"] >= MIN_RECALL_HARD) & (model_df["FPR"] <= MAX_FPR_OPERATING)
    ]
    if not relaxed.empty:
        return (_rank_balanced_operating_points(relaxed).iloc[0], 1)

    recall_ok = model_df[model_df["Recall"] >= MIN_RECALL_HARD]
    if not recall_ok.empty:
        return (_rank_balanced_operating_points(recall_ok).iloc[0], 2)

    return (_rank_balanced_operating_points(model_df).iloc[0], 3)


def _build_risk_bin_table(y_true: pd.Series, y_proba: np.ndarray) -> pd.DataFrame:
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


MODEL_CANDIDATE_NAMES: tuple[str, ...] = (
    "LogisticRegression",
    "RandomForest",
    "GradientBoosting",
    "XGBoostCalibratedTuned",
    "XGBoostDeep",
)


def model_catalog() -> dict[str, Pipeline | RandomForestClassifier | CalibratedClassifierCV | XGBClassifier]:
    """Return the fixed candidate set used by training, notebook, and pipeline."""
    all_candidates: dict[str, Pipeline | RandomForestClassifier | CalibratedClassifierCV | XGBClassifier] = {
        "LogisticRegression": Pipeline(
            steps=[
                ("scaler", StandardScaler()),
                (
                    "model",
                    LogisticRegression(
                        random_state=RANDOM_STATE,
                        class_weight="balanced",
                        max_iter=3000,
                    ),
                ),
            ]
        ),
        "RandomForest": RandomForestClassifier(
            n_estimators=250,
            max_depth=12,
            random_state=RANDOM_STATE,
            class_weight="balanced_subsample",
            n_jobs=-1,
        ),
        "GradientBoosting": GradientBoostingClassifier(
            random_state=RANDOM_STATE,
            n_estimators=180,
            learning_rate=0.05,
            max_depth=3,
        ),
        "XGBoostCalibratedTuned": CalibratedClassifierCV(
            estimator=XGBClassifier(
                n_estimators=320,
                max_depth=4,
                learning_rate=0.045,
                subsample=0.92,
                colsample_bytree=0.92,
                reg_lambda=1.3,
                scale_pos_weight=2.6,
                eval_metric="logloss",
                random_state=RANDOM_STATE,
                n_jobs=-1,
            ),
            method="sigmoid",
            cv=3,
        ),
        "XGBoostDeep": XGBClassifier(
            n_estimators=520,
            max_depth=7,
            learning_rate=0.028,
            subsample=0.86,
            colsample_bytree=0.82,
            colsample_bylevel=0.82,
            reg_alpha=0.5,
            reg_lambda=2.0,
            min_child_weight=6,
            gamma=0.10,
            eval_metric="logloss",
            random_state=RANDOM_STATE,
            n_jobs=-1,
            scale_pos_weight=2.4,
        ),
    }
    missing = [name for name in MODEL_CANDIDATE_NAMES if name not in all_candidates]
    if missing:
        raise ValueError(f"MODEL_CANDIDATE_NAMES references unknown models: {missing}")
    return {name: all_candidates[name] for name in MODEL_CANDIDATE_NAMES}


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


OPERATING_TIER_LABELS: dict[int, str] = {
    0: "All gates pass",
    1: "Recall + FPR OK (precision/F1 relaxed)",
    2: "Recall OK only",
    3: "Fallback — no recall floor met",
}


def policy_thresholds() -> dict[str, float]:
    return {
        "recall_hard_min": MIN_RECALL_HARD,
        "recall_target": TARGET_RECALL,
        "precision_min": TARGET_PRECISION,
        "f1_min": TARGET_F1,
        "fpr_max_operating": MAX_FPR_OPERATING,
        "fixed_comparison_threshold": THRESHOLD,
    }


def evaluate_policy_gates(recall: float, precision: float, f1: float, fpr: float) -> dict[str, bool]:
    return {
        "recall_hard": recall >= MIN_RECALL_HARD,
        "fpr": fpr <= MAX_FPR_OPERATING,
        "precision": precision >= TARGET_PRECISION,
        "f1": f1 >= TARGET_F1,
    }


def build_fixed_threshold_gate_table(results_df: pd.DataFrame) -> pd.DataFrame:
    """Mark pass/fail at the fixed comparison threshold (default 0.18)."""
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
                "Threshold": THRESHOLD,
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


def add_sequential_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.sort_values(["athlete_id", "date"]).copy()
    grouped = out.groupby("athlete_id", group_keys=False)
    out["acwr_ratio_ma7"] = grouped["acwr_ratio"].transform(
        lambda x: x.rolling(7, min_periods=1).mean()
    )
    out["sleep_hours_ma7"] = grouped["sleep_hours"].transform(
        lambda x: x.rolling(7, min_periods=1).mean()
    )
    return out


def extract_feature_importance(model, feature_names: list[str]) -> pd.DataFrame | None:
    base_model = model
    if isinstance(model, Pipeline):
        base_model = model.named_steps["model"]
    elif isinstance(model, CalibratedClassifierCV):
        calibrated = model.calibrated_classifiers_
        if calibrated and hasattr(calibrated[0], "estimator"):
            base_model = calibrated[0].estimator
    if hasattr(base_model, "feature_importances_"):
        return pd.DataFrame(
            {"feature": feature_names, "importance": base_model.feature_importances_}
        ).sort_values("importance", ascending=False)
    if hasattr(base_model, "coef_"):
        return pd.DataFrame(
            {"feature": feature_names, "importance": np.abs(base_model.coef_[0])}
        ).sort_values("importance", ascending=False)
    return None


def _project_relative_path(path: str, project_root: str) -> str:
    """Store artifact paths relative to the repo root for portability."""
    return os.path.relpath(path, project_root).replace("\\", "/")


@dataclass
class TrainSplit:
    X_train: pd.DataFrame
    X_test: pd.DataFrame
    y_train: pd.Series
    y_test: pd.Series
    y_all: pd.Series
    feature_columns: list[str]
    holdout_athlete_ids: set[int]


@dataclass
class TrainResult:
    results_df: pd.DataFrame
    threshold_rows: list[dict[str, float | str]]
    trained_models: dict[str, object]
    calibration_bins: dict[str, pd.DataFrame]
    best_row: pd.Series
    best_model_name: str
    best_model: object
    best_operating_threshold: float
    winner_operating_metrics: dict[str, float]
    risk_bins_df: pd.DataFrame
    importance_df: pd.DataFrame | None
    best_points: pd.DataFrame


def load_dataset(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    if LABEL_COLUMN not in df.columns and LEGACY_LABEL_COLUMN in df.columns:
        df = df.rename(columns={LEGACY_LABEL_COLUMN: LABEL_COLUMN})
    return df


def subset_dataset(
    df: pd.DataFrame,
    *,
    n_athletes: int,
    max_days_per_athlete: int | None = None,
    seed: int = RANDOM_STATE,
) -> pd.DataFrame:
    """Sample athletes (and optionally trim days) for fast notebook demos."""
    athletes = pd.Series(df["athlete_id"].dropna().unique()).sort_values().reset_index(drop=True)
    sample_n = min(n_athletes, len(athletes))
    chosen = set(athletes.sample(n=sample_n, random_state=seed).astype(int).tolist())
    out = df[df["athlete_id"].astype(int).isin(chosen)].copy()
    if max_days_per_athlete is not None:
        out = (
            out.sort_values(["athlete_id", "date"])
            .groupby("athlete_id", group_keys=False)
            .head(max_days_per_athlete)
        )
    return out.sort_values(["athlete_id", "date"]).reset_index(drop=True)


def prepare_model_frames(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, list[str]]:
    if LABEL_COLUMN not in df.columns and LEGACY_LABEL_COLUMN in df.columns:
        df = df.rename(columns={LEGACY_LABEL_COLUMN: LABEL_COLUMN})
    df = add_sequential_features(df)
    y = df[LABEL_COLUMN].astype(int)
    model_df = df.drop(columns=[LABEL_COLUMN, "athlete_id", "date"])
    feature_columns = list(model_df.columns)
    return df, y, model_df, feature_columns


def make_train_split(
    df: pd.DataFrame,
    *,
    holdout_ratio: float = 0.2,
    seed: int = RANDOM_STATE,
    benchmark_path: str | Path | None = None,
) -> TrainSplit:
    df, y, model_df, feature_columns = prepare_model_frames(df)
    benchmark_file = Path(benchmark_path) if benchmark_path else None
    if benchmark_file is not None and benchmark_file.is_file():
        benchmark_df = pd.read_csv(benchmark_file, parse_dates=["date"])
        benchmark_df = add_sequential_features(benchmark_df)
        holdout_ids = set(benchmark_df["athlete_id"].astype(int).unique().tolist())
        train_mask = ~df["athlete_id"].astype(int).isin(holdout_ids)
        test_mask = df["athlete_id"].astype(int).isin(holdout_ids)
    else:
        athletes = pd.Series(df["athlete_id"].dropna().unique()).sort_values().reset_index(drop=True)
        sample_n = max(1, int(len(athletes) * holdout_ratio))
        holdout_ids = set(athletes.sample(n=sample_n, random_state=seed).astype(int).tolist())
        train_mask = ~df["athlete_id"].astype(int).isin(holdout_ids)
        test_mask = df["athlete_id"].astype(int).isin(holdout_ids)
    if train_mask.sum() == 0 or test_mask.sum() == 0:
        raise ValueError("Holdout split invalid: empty train or test after athlete split.")
    return TrainSplit(
        X_train=model_df.loc[train_mask],
        X_test=model_df.loc[test_mask],
        y_train=y.loc[train_mask],
        y_test=y.loc[test_mask],
        y_all=y,
        feature_columns=feature_columns,
        holdout_athlete_ids=holdout_ids,
    )


def train_and_compare(
    split: TrainSplit,
    *,
    model_names: list[str] | None = None,
    verbose: bool = True,
) -> TrainResult:
    catalog = model_catalog()
    if model_names is not None:
        missing = [name for name in model_names if name not in catalog]
        if missing:
            raise ValueError(f"Unknown model names: {missing}")
        catalog = {name: catalog[name] for name in model_names}

    if verbose:
        print_split_diagnostics(split.y_all, split.y_train, split.y_test)

    results: list[dict[str, float | str]] = []
    trained_models: dict[str, object] = {}
    calibration_bins: dict[str, pd.DataFrame] = {}
    threshold_rows: list[dict[str, float | str]] = []

    for model_name, model in catalog.items():
        if verbose:
            print(f"Training {model_name}...")
        model.fit(split.X_train, split.y_train)
        y_proba = model.predict_proba(split.X_test)[:, 1]
        metrics = evaluate_with_threshold(split.y_test, y_proba, THRESHOLD)
        pr_precision, pr_recall, _ = precision_recall_curve(split.y_test, y_proba)
        pr_auc = auc(pr_recall, pr_precision)
        metrics.update(
            {
                "Model": model_name,
                "ROC-AUC": roc_auc_score(split.y_test, y_proba),
                "PR-AUC": pr_auc,
                "LogLoss": log_loss(split.y_test, y_proba, labels=[0, 1]),
                "BrierScore": brier_score_loss(split.y_test, y_proba),
                "BalancedAccuracy@Threshold": balanced_accuracy_score(
                    split.y_test, (y_proba >= THRESHOLD).astype(int)
                ),
            }
        )
        results.append(metrics)
        trained_models[model_name] = model
        threshold_rows.extend(threshold_sweep(split.y_test, y_proba, model_name))

        frac_pos, mean_pred = calibration_curve(split.y_test, y_proba, n_bins=10, strategy="uniform")
        calibration_bins[model_name] = pd.DataFrame(
            {"mean_predicted_risk": mean_pred, "fraction_positive": frac_pos}
        )

    results_df = pd.DataFrame(results).sort_values(
        by=["F1@Threshold", "Precision@Threshold", "Recall@Threshold", "FPR@Threshold"],
        ascending=[False, False, False, True],
    )
    best_row = pick_best_model(results_df, threshold_rows)
    best_model_name = str(best_row["Model"])
    best_model = trained_models[best_model_name]
    best_operating_threshold = select_operating_threshold_for_model(threshold_rows, best_model_name)
    winner_proba = best_model.predict_proba(split.X_test)[:, 1]
    winner_operating_metrics = evaluate_with_threshold(
        split.y_test, winner_proba, best_operating_threshold
    )
    risk_bins_df = _build_risk_bin_table(split.y_test, winner_proba)
    importance_df = extract_feature_importance(best_model, split.feature_columns)
    best_points = select_best_operating_points(threshold_rows)

    return TrainResult(
        results_df=results_df,
        threshold_rows=threshold_rows,
        trained_models=trained_models,
        calibration_bins=calibration_bins,
        best_row=best_row,
        best_model_name=best_model_name,
        best_model=best_model,
        best_operating_threshold=best_operating_threshold,
        winner_operating_metrics=winner_operating_metrics,
        risk_bins_df=risk_bins_df,
        importance_df=importance_df,
        best_points=best_points,
    )


def save_training_artifacts(
    result: TrainResult,
    split: TrainSplit,
    *,
    artifacts_dir: str | Path,
    dataset_path: str | Path,
    project_root: str | Path,
    benchmark_path: str | Path | None = None,
    dataset_rows: int | None = None,
) -> Path:
    artifacts_dir = Path(artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    run_id = artifacts_dir.name
    output_model_path = artifacts_dir / "injury_model.pkl"
    model_bundle = {
        "estimator": result.best_model,
        "feature_columns": split.feature_columns,
        "threshold": result.best_operating_threshold,
        "medium_threshold": max(0.15, result.best_operating_threshold * 0.6),
        "policy": {
            "recall_hard_min": MIN_RECALL_HARD,
            "recall_min": TARGET_RECALL,
            "fpr_max_operating": MAX_FPR_OPERATING,
            "precision_min": TARGET_PRECISION,
            "f1_min": TARGET_F1,
        },
        "winner": result.best_model_name,
    }
    joblib.dump(model_bundle, output_model_path)

    result.results_df.to_csv(artifacts_dir / "model_comparison.csv", index=False)
    pd.concat(
        [frame.assign(model=name) for name, frame in result.calibration_bins.items()],
        ignore_index=True,
    ).to_csv(artifacts_dir / "calibration_curve_data.csv", index=False)
    pd.DataFrame(result.threshold_rows).to_csv(artifacts_dir / "threshold_sweep.csv", index=False)
    result.best_points.to_csv(artifacts_dir / "best_operating_points.csv", index=False)
    result.risk_bins_df.to_csv(artifacts_dir / "risk_bins_summary.csv", index=False)

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "artifacts_dir": _project_relative_path(str(artifacts_dir), str(project_root)),
        "dataset_path": _project_relative_path(str(dataset_path), str(project_root)),
        "dataset_rows": int(dataset_rows if dataset_rows is not None else len(split.y_all)),
        "benchmark_path": (
            _project_relative_path(str(benchmark_path), str(project_root))
            if benchmark_path and Path(benchmark_path).is_file()
            else None
        ),
        "threshold": result.best_operating_threshold,
        "policy": model_bundle["policy"],
        "winner": result.best_model_name,
        "winner_metrics": {
            "Recall@Threshold": float(result.winner_operating_metrics["Recall@Threshold"]),
            "Precision@Threshold": float(result.winner_operating_metrics["Precision@Threshold"]),
            "F1@Threshold": float(result.winner_operating_metrics["F1@Threshold"]),
            "FPR@Threshold": float(result.winner_operating_metrics["FPR@Threshold"]),
            "BrierScore": float(result.best_row["BrierScore"]),
            "ROC-AUC": float(result.best_row["ROC-AUC"]),
            "LogLoss": float(result.best_row["LogLoss"]),
        },
        "risk_bins": [
            {
                "bin": str(row["bin"]),
                "samples": int(row["samples"]),
                "injury_rate": float(row["injury_rate"]),
            }
            for _, row in result.risk_bins_df.iterrows()
        ],
    }
    manifest_path = artifacts_dir / "run_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    if result.importance_df is not None:
        result.importance_df.to_csv(artifacts_dir / "feature_importance.csv", index=False)

    return artifacts_dir


def main() -> None:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    dataset_path = os.path.join(script_dir, "athlete_injury_data.csv")
    benchmark_path = os.path.join(script_dir, "benchmark_holdout.csv")
    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"{dataset_path} not found. Run data_generator.py first.")

    df = load_dataset(dataset_path)
    split = make_train_split(
        df,
        benchmark_path=benchmark_path if os.path.exists(benchmark_path) else None,
    )
    result = train_and_compare(split, verbose=True)

    print("\nModel comparison:")
    print(result.results_df.to_string(index=False))
    print("\nThreshold sweep summary:")
    print(pd.DataFrame(result.threshold_rows).sort_values(by=["Model", "Threshold"]).to_string(index=False))
    print("\nBest operating points per model:")
    print(result.best_points.to_string(index=False))
    print(f"\nSelected winner: {result.best_model_name}")
    print(
        f"  @ threshold {result.best_operating_threshold:.2f}: "
        f"Recall={result.winner_operating_metrics['Recall@Threshold']:.3f}, "
        f"Precision={result.winner_operating_metrics['Precision@Threshold']:.3f}, "
        f"F1={result.winner_operating_metrics['F1@Threshold']:.3f}, "
        f"FPR={result.winner_operating_metrics['FPR@Threshold']:.3f}"
    )

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    artifacts_dir = os.path.join(script_dir, "artifacts", run_id)
    save_training_artifacts(
        result,
        split,
        artifacts_dir=artifacts_dir,
        dataset_path=dataset_path,
        project_root=project_root,
        benchmark_path=benchmark_path if os.path.exists(benchmark_path) else None,
        dataset_rows=len(df),
    )

    print(f"\nSaved model bundle: {os.path.join(artifacts_dir, 'injury_model.pkl')}")
    print(f"Saved comparison: {os.path.join(artifacts_dir, 'model_comparison.csv')}")
    print(f"Saved calibration data: {os.path.join(artifacts_dir, 'calibration_curve_data.csv')}")
    print(f"Saved threshold sweep: {os.path.join(artifacts_dir, 'threshold_sweep.csv')}")
    print(f"Saved best operating points: {os.path.join(artifacts_dir, 'best_operating_points.csv')}")
    print(f"Saved risk bins summary: {os.path.join(artifacts_dir, 'risk_bins_summary.csv')}")
    print(f"Saved run manifest: {os.path.join(artifacts_dir, 'run_manifest.json')}")


if __name__ == "__main__":
    main()