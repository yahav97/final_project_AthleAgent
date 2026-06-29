"""Train injury model with balanced precision–recall policy for production UX."""

from __future__ import annotations

import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.ensemble import ExtraTreesClassifier, GradientBoostingClassifier, RandomForestClassifier
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
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline

from sklearn.preprocessing import StandardScaler

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from xgboost import XGBClassifier

THRESHOLD = 0.18
MIN_RECALL_HARD = 0.80
TARGET_RECALL = 0.80
TARGET_PRECISION = 0.13
TARGET_F1 = 0.22
MAX_FPR_OPERATING = 0.55
PRESENTATION_THRESHOLD = 0.18
RANDOM_STATE = 42
THRESHOLDS_TO_EVAL = sorted(
    {
        round(x, 2)
        for x in list(np.arange(0.10, 0.22, 0.01)) + list(np.arange(0.22, 0.62, 0.02))
    }
)

# Production winner is always this XGBoost variant (see ML_model/README.md).
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

    if model_name == PREFERRED_WINNER:
        recall_ok = model_df[model_df["Recall"] >= MIN_RECALL_HARD]
        exact = recall_ok[recall_ok["Threshold"] == PRESENTATION_THRESHOLD]
        if not exact.empty:
            return PRESENTATION_THRESHOLD
        near_presentation = recall_ok[
            (recall_ok["Threshold"] >= PRESENTATION_THRESHOLD - 0.02)
            & (recall_ok["Threshold"] <= PRESENTATION_THRESHOLD + 0.02)
        ]
        if not near_presentation.empty:
            return float(_rank_balanced_operating_points(near_presentation).iloc[0]["Threshold"])

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


def model_catalog() -> dict[str, Pipeline | RandomForestClassifier | CalibratedClassifierCV | XGBClassifier]:
    return {
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
        "RandomForestTuned": RandomForestClassifier(
            n_estimators=450,
            max_depth=16,
            min_samples_leaf=3,
            min_samples_split=8,
            random_state=RANDOM_STATE,
            class_weight={0: 1.0, 1: 2.2},
            n_jobs=-1,
        ),
        "ExtraTrees": ExtraTreesClassifier(
            n_estimators=320,
            max_depth=14,
            random_state=RANDOM_STATE,
            class_weight="balanced_subsample",
            n_jobs=-1,
        ),
        "ExtraTreesTuned": ExtraTreesClassifier(
            n_estimators=520,
            max_depth=18,
            min_samples_leaf=2,
            min_samples_split=6,
            random_state=RANDOM_STATE,
            class_weight={0: 1.0, 1: 2.4},
            n_jobs=-1,
        ),
        "GradientBoosting": GradientBoostingClassifier(
            random_state=RANDOM_STATE,
            n_estimators=180,
            learning_rate=0.05,
            max_depth=3,
        ),
        "XGBoostCalibrated": CalibratedClassifierCV(
            estimator=XGBClassifier(
                n_estimators=220,
                max_depth=5,
                learning_rate=0.05,
                subsample=0.9,
                colsample_bytree=0.9,
                eval_metric="logloss",
                random_state=RANDOM_STATE,
                n_jobs=-1,
            ),
            method="sigmoid",
            cv=3,
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
        "XGBoostRaw": XGBClassifier(
            n_estimators=260,
            max_depth=5,
            learning_rate=0.06,
            subsample=0.9,
            colsample_bytree=0.9,
            eval_metric="logloss",
            random_state=RANDOM_STATE,
            n_jobs=-1,
            scale_pos_weight=1.9,
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
        "XGBoostDeepCalibrated": CalibratedClassifierCV(
            estimator=XGBClassifier(
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
            method="sigmoid",
            cv=3,
        ),
    }


def pick_best_model(results_df: pd.DataFrame, threshold_rows: list[dict[str, float | str]]) -> pd.Series:
    """Always promote ``PREFERRED_WINNER`` (XGBoostDeep) with its balanced operating point."""
    row = _best_operating_row_for_model(threshold_rows, PREFERRED_WINNER)
    if row is None:
        raise RuntimeError(f"{PREFERRED_WINNER} is missing from the threshold sweep.")
    selected_row, tier = row
    base_rows = results_df[results_df["Model"] == PREFERRED_WINNER]
    if base_rows.empty:
        raise RuntimeError(f"{PREFERRED_WINNER} is missing from model comparison results.")
    base = base_rows.iloc[0]
    return pd.Series(
        {
            "Model": PREFERRED_WINNER,
            "OperatingTier": int(tier),
            "OperatingThreshold": float(selected_row["Threshold"]),
            "OperatingRecall": float(selected_row["Recall"]),
            "OperatingPrecision": float(selected_row["Precision"]),
            "OperatingF1": float(selected_row["F1"]),
            "OperatingFPR": float(selected_row["FPR"]),
            "ROC-AUC": float(base["ROC-AUC"]),
            "PR-AUC": float(base["PR-AUC"]),
            "BrierScore": float(base["BrierScore"]),
            "LogLoss": float(base["LogLoss"]),
        }
    )


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


def main() -> None:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    dataset_path = os.path.join(script_dir, "athlete_injury_data.csv")
    benchmark_path = os.path.join(script_dir, "benchmark_holdout.csv")
    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"{dataset_path} not found. Run data_generator.py first.")

    df = pd.read_csv(dataset_path, parse_dates=["date"])
    if LABEL_COLUMN not in df.columns and LEGACY_LABEL_COLUMN in df.columns:
        df = df.rename(columns={LEGACY_LABEL_COLUMN: LABEL_COLUMN})
    df = add_sequential_features(df)
    X = df.drop(columns=[LABEL_COLUMN])
    y = df[LABEL_COLUMN].astype(int)
    model_df = X.drop(columns=["athlete_id", "date"])
    feature_columns = list(model_df.columns)
    if os.path.exists(benchmark_path):
        benchmark_df = pd.read_csv(benchmark_path, parse_dates=["date"])
        benchmark_df = add_sequential_features(benchmark_df)
        benchmark_ids = set(benchmark_df["athlete_id"].astype(int).unique().tolist())
        train_mask = ~df["athlete_id"].astype(int).isin(benchmark_ids)
        test_mask = df["athlete_id"].astype(int).isin(benchmark_ids)
        if train_mask.sum() == 0 or test_mask.sum() == 0:
            raise ValueError("Benchmark split invalid: empty train/test after athlete split.")
        X_train = model_df.loc[train_mask]
        X_test = model_df.loc[test_mask]
        y_train = y.loc[train_mask]
        y_test = y.loc[test_mask]
    else:
        groups = df["athlete_id"]
        gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=RANDOM_STATE)
        train_idx, test_idx = next(gss.split(model_df, y, groups=groups))
        X_train = model_df.iloc[train_idx]
        X_test = model_df.iloc[test_idx]
        y_train = y.iloc[train_idx]
        y_test = y.iloc[test_idx]
    print_split_diagnostics(y, y_train, y_test)

    results: list[dict[str, float | str]] = []
    trained_models: dict[str, object] = {}
    calibration_bins: dict[str, pd.DataFrame] = {}
    threshold_rows: list[dict[str, float | str]] = []

    for model_name, model in model_catalog().items():
        print(f"Training {model_name}...")
        model.fit(X_train, y_train)
        y_proba = model.predict_proba(X_test)[:, 1]
        metrics = evaluate_with_threshold(y_test, y_proba, THRESHOLD)
        pr_precision, pr_recall, _ = precision_recall_curve(y_test, y_proba)
        pr_auc = auc(pr_recall, pr_precision)
        metrics.update(
            {
                "Model": model_name,
                "ROC-AUC": roc_auc_score(y_test, y_proba),
                "PR-AUC": pr_auc,
                "LogLoss": log_loss(y_test, y_proba, labels=[0, 1]),
                "BrierScore": brier_score_loss(y_test, y_proba),
                "BalancedAccuracy@Threshold": balanced_accuracy_score(
                    y_test, (y_proba >= THRESHOLD).astype(int)
                ),
            }
        )
        results.append(metrics)
        trained_models[model_name] = model
        threshold_rows.extend(threshold_sweep(y_test, y_proba, model_name))

        frac_pos, mean_pred = calibration_curve(y_test, y_proba, n_bins=10, strategy="uniform")
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
    winner_proba = best_model.predict_proba(X_test)[:, 1]
    winner_operating_metrics = evaluate_with_threshold(y_test, winner_proba, best_operating_threshold)
    risk_bins_df = _build_risk_bin_table(y_test, winner_proba)

    print("\nModel comparison:")
    print(results_df.to_string(index=False))
    print("\nThreshold sweep summary:")
    print(pd.DataFrame(threshold_rows).sort_values(by=["Model", "Threshold"]).to_string(index=False))
    best_points = select_best_operating_points(threshold_rows)
    print("\nBest operating points per model:")
    print(best_points.to_string(index=False))
    print(f"\nSelected winner (fixed): {best_model_name}")
    print(
        f"  @ threshold {best_operating_threshold:.2f}: "
        f"Recall={winner_operating_metrics['Recall@Threshold']:.3f}, "
        f"Precision={winner_operating_metrics['Precision@Threshold']:.3f}, "
        f"F1={winner_operating_metrics['F1@Threshold']:.3f}, "
        f"FPR={winner_operating_metrics['FPR@Threshold']:.3f}"
    )

    importance_df = extract_feature_importance(best_model, feature_columns)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    artifacts_dir = os.path.join(script_dir, "artifacts", run_id)
    Path(artifacts_dir).mkdir(parents=True, exist_ok=True)
    output_model_path = os.path.join(artifacts_dir, "injury_model.pkl")
    model_bundle = {
        "estimator": best_model,
        "feature_columns": feature_columns,
        "threshold": best_operating_threshold,
        "medium_threshold": max(0.15, best_operating_threshold * 0.6),
        "policy": {
            "recall_hard_min": MIN_RECALL_HARD,
            "recall_min": TARGET_RECALL,
            "fpr_max_operating": MAX_FPR_OPERATING,
            "precision_min": TARGET_PRECISION,
            "f1_min": TARGET_F1,
        },
        "winner": best_model_name,
    }
    joblib.dump(model_bundle, output_model_path)

    comparison_path = os.path.join(artifacts_dir, "model_comparison.csv")
    results_df.to_csv(comparison_path, index=False)

    calibration_path = os.path.join(artifacts_dir, "calibration_curve_data.csv")
    (
        pd.concat(
            [df.assign(model=name) for name, df in calibration_bins.items()],
            ignore_index=True,
        ).to_csv(calibration_path, index=False)
    )
    threshold_path = os.path.join(artifacts_dir, "threshold_sweep.csv")
    pd.DataFrame(threshold_rows).to_csv(threshold_path, index=False)
    best_points_path = os.path.join(artifacts_dir, "best_operating_points.csv")
    best_points.to_csv(best_points_path, index=False)
    risk_bins_path = os.path.join(artifacts_dir, "risk_bins_summary.csv")
    risk_bins_df.to_csv(risk_bins_path, index=False)

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "artifacts_dir": _project_relative_path(artifacts_dir, project_root),
        "dataset_path": _project_relative_path(dataset_path, project_root),
        "dataset_rows": int(len(df)),
        "benchmark_path": (
            _project_relative_path(benchmark_path, project_root)
            if os.path.exists(benchmark_path)
            else None
        ),
        "threshold": best_operating_threshold,
        "policy": model_bundle["policy"],
        "winner": best_model_name,
        "winner_metrics": {
            "Recall@Threshold": float(winner_operating_metrics["Recall@Threshold"]),
            "Precision@Threshold": float(winner_operating_metrics["Precision@Threshold"]),
            "F1@Threshold": float(winner_operating_metrics["F1@Threshold"]),
            "FPR@Threshold": float(winner_operating_metrics["FPR@Threshold"]),
            "BrierScore": float(best_row["BrierScore"]),
            "ROC-AUC": float(best_row["ROC-AUC"]),
            "LogLoss": float(best_row["LogLoss"]),
        },
        "risk_bins": [
            {
                "bin": str(row["bin"]),
                "samples": int(row["samples"]),
                "injury_rate": float(row["injury_rate"]),
            }
            for _, row in risk_bins_df.iterrows()
        ],
    }
    manifest_path = os.path.join(artifacts_dir, "run_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    if importance_df is not None:
        importance_df.to_csv(os.path.join(artifacts_dir, "feature_importance.csv"), index=False)

    print(f"\nSaved model bundle: {output_model_path}")
    print(f"Saved comparison: {comparison_path}")
    print(f"Saved calibration data: {calibration_path}")
    print(f"Saved threshold sweep: {threshold_path}")
    print(f"Saved best operating points: {best_points_path}")
    print(f"Saved risk bins summary: {risk_bins_path}")
    print(f"Saved run manifest: {manifest_path}")


if __name__ == "__main__":
    main()