"""Train injury model with recall-first policy and calibrated probabilities."""

from __future__ import annotations

import io
import json
import os
import sys
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.ensemble import ExtraTreesClassifier, GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    balanced_accuracy_score,
    f1_score,
    log_loss,
    precision_recall_curve,
    auc,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from xgboost import XGBClassifier

THRESHOLD = 0.4
TARGET_RECALL = 0.90
TARGET_RECALL_HIGH = 0.95
TARGET_PRECISION = 0.30
TARGET_F1 = 0.45
RANDOM_STATE = 42
THRESHOLDS_TO_EVAL = [round(x, 2) for x in np.arange(0.20, 0.62, 0.02)]


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
            df.sort_values(by=["Recall", "F1", "Precision", "FPR"], ascending=[False, False, False, True])
            .groupby("Model")
            .head(1)
        )
    return (
        feasible.sort_values(by=["Recall", "F1", "Precision", "FPR"], ascending=[False, False, False, True])
        .groupby("Model")
        .head(1)
        .sort_values(by=["Recall", "F1", "Precision", "FPR"], ascending=[False, False, False, True])
    )


def select_operating_threshold_for_model(
    threshold_rows: list[dict[str, float | str]],
    model_name: str,
) -> float:
    df = pd.DataFrame(threshold_rows)
    model_df = df[df["Model"] == model_name].copy()
    if model_df.empty:
        return THRESHOLD

    high_recall = model_df[model_df["Recall"] >= TARGET_RECALL_HIGH]
    if not high_recall.empty:
        ranked = high_recall.sort_values(
            by=["Precision", "F1", "FPR", "Threshold"],
            ascending=[False, False, True, True],
        )
        return float(ranked.iloc[0]["Threshold"])

    min_recall = model_df[model_df["Recall"] >= TARGET_RECALL]
    if not min_recall.empty:
        ranked = min_recall.sort_values(
            by=["Precision", "F1", "FPR", "Threshold"],
            ascending=[False, False, True, True],
        )
        return float(ranked.iloc[0]["Threshold"])

    fallback = model_df.sort_values(
        by=["Recall", "F1", "Precision", "FPR", "Threshold"],
        ascending=[False, False, False, True, True],
    ).iloc[0]
    return float(fallback["Threshold"])


def model_catalog() -> dict[str, Pipeline | RandomForestClassifier | CalibratedClassifierCV]:
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
            class_weight={0: 1.0, 1: 2.6},
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
            class_weight={0: 1.0, 1: 2.9},
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
                scale_pos_weight=3.0,
                eval_metric="logloss",
                random_state=RANDOM_STATE,
                n_jobs=-1,
            ),
            method="sigmoid",
            cv=3,
        ),
    }


def pick_best_model(results_df: pd.DataFrame) -> pd.Series:
    guarded = results_df[
        (results_df["Recall@Threshold"] >= TARGET_RECALL)
        & (results_df["Precision@Threshold"] >= TARGET_PRECISION)
        & (results_df["F1@Threshold"] >= TARGET_F1)
    ]
    source = guarded if not guarded.empty else results_df
    return source.sort_values(
        by=["Recall@Threshold", "F1@Threshold", "Precision@Threshold", "FPR@Threshold", "ROC-AUC"],
        ascending=[False, False, False, True, False],
    ).iloc[0]


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


def main() -> None:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    dataset_path = os.path.join(script_dir, "athlete_injury_data.csv")
    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"{dataset_path} not found. Run data_generator.py first.")

    df = pd.read_csv(dataset_path)
    X = df.drop(columns=["injury_tomorrow"])
    y = df["injury_tomorrow"].astype(int)
    feature_columns = list(X.columns)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )
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
        by=["Recall@Threshold", "F1@Threshold", "Precision@Threshold", "FPR@Threshold"],
        ascending=[False, False, False, True],
    )
    best_row = pick_best_model(results_df)
    best_model_name = str(best_row["Model"])
    best_model = trained_models[best_model_name]
    best_operating_threshold = select_operating_threshold_for_model(threshold_rows, best_model_name)
    winner_proba = best_model.predict_proba(X_test)[:, 1]
    winner_operating_metrics = evaluate_with_threshold(y_test, winner_proba, best_operating_threshold)

    print("\nModel comparison:")
    print(results_df.to_string(index=False))
    print("\nThreshold sweep summary:")
    print(pd.DataFrame(threshold_rows).sort_values(by=["Model", "Threshold"]).to_string(index=False))
    best_points = select_best_operating_points(threshold_rows)
    print("\nBest operating points per model:")
    print(best_points.to_string(index=False))
    print(f"\nSelected winner: {best_model_name}")

    importance_df = extract_feature_importance(best_model, feature_columns)

    output_model_path = os.path.join(project_root, "backend", "injury_model.pkl")
    model_bundle = {
        "estimator": best_model,
        "feature_columns": feature_columns,
        "threshold": best_operating_threshold,
        "policy": {
            "recall_min": TARGET_RECALL,
            "recall_high_target": TARGET_RECALL_HIGH,
            "precision_min": TARGET_PRECISION,
            "f1_min": TARGET_F1,
        },
        "winner": best_model_name,
    }
    joblib.dump(model_bundle, output_model_path)

    comparison_path = os.path.join(script_dir, "model_comparison.csv")
    results_df.to_csv(comparison_path, index=False)

    calibration_path = os.path.join(script_dir, "calibration_curve_data.csv")
    (
        pd.concat(
            [df.assign(model=name) for name, df in calibration_bins.items()],
            ignore_index=True,
        ).to_csv(calibration_path, index=False)
    )
    threshold_path = os.path.join(script_dir, "threshold_sweep.csv")
    pd.DataFrame(threshold_rows).to_csv(threshold_path, index=False)
    best_points_path = os.path.join(script_dir, "best_operating_points.csv")
    best_points.to_csv(best_points_path, index=False)

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_path": dataset_path,
        "dataset_rows": int(len(df)),
        "threshold": best_operating_threshold,
        "policy": model_bundle["policy"],
        "winner": best_model_name,
        "winner_metrics": {
            "Recall@Threshold": float(winner_operating_metrics["Recall@Threshold"]),
            "Precision@Threshold": float(winner_operating_metrics["Precision@Threshold"]),
            "F1@Threshold": float(winner_operating_metrics["F1@Threshold"]),
            "FPR@Threshold": float(winner_operating_metrics["FPR@Threshold"]),
            "ROC-AUC": float(best_row["ROC-AUC"]),
            "LogLoss": float(best_row["LogLoss"]),
        },
    }
    manifest_path = os.path.join(script_dir, "run_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    if importance_df is not None:
        importance_df.to_csv(os.path.join(script_dir, "feature_importance.csv"), index=False)

    print(f"\nSaved model bundle: {output_model_path}")
    print(f"Saved comparison: {comparison_path}")
    print(f"Saved calibration data: {calibration_path}")
    print(f"Saved threshold sweep: {threshold_path}")
    print(f"Saved best operating points: {best_points_path}")
    print(f"Saved run manifest: {manifest_path}")


if __name__ == "__main__":
    main()