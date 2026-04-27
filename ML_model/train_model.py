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
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    f1_score,
    log_loss,
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
TARGET_PRECISION = 0.30
TARGET_F1 = 0.45
RANDOM_STATE = 42


def evaluate_with_threshold(y_true: pd.Series, y_proba: np.ndarray, threshold: float) -> dict[str, float]:
    y_pred = (y_proba >= threshold).astype(int)
    return {
        "Recall@Threshold": recall_score(y_true, y_pred, zero_division=0),
        "Precision@Threshold": precision_score(y_true, y_pred, zero_division=0),
        "F1@Threshold": f1_score(y_true, y_pred, zero_division=0),
    }


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
    }


def pick_best_model(results_df: pd.DataFrame) -> pd.Series:
    guarded = results_df[
        (results_df["Recall@Threshold"] >= TARGET_RECALL)
        & (results_df["Precision@Threshold"] >= TARGET_PRECISION)
        & (results_df["F1@Threshold"] >= TARGET_F1)
    ]
    source = guarded if not guarded.empty else results_df
    return source.sort_values(
        by=["Recall@Threshold", "F1@Threshold", "Precision@Threshold", "ROC-AUC"],
        ascending=False,
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

    results: list[dict[str, float | str]] = []
    trained_models: dict[str, object] = {}
    calibration_bins: dict[str, pd.DataFrame] = {}

    for model_name, model in model_catalog().items():
        print(f"Training {model_name}...")
        model.fit(X_train, y_train)
        y_proba = model.predict_proba(X_test)[:, 1]
        metrics = evaluate_with_threshold(y_test, y_proba, THRESHOLD)
        metrics.update(
            {
                "Model": model_name,
                "ROC-AUC": roc_auc_score(y_test, y_proba),
                "LogLoss": log_loss(y_test, y_proba, labels=[0, 1]),
            }
        )
        results.append(metrics)
        trained_models[model_name] = model

        frac_pos, mean_pred = calibration_curve(y_test, y_proba, n_bins=10, strategy="uniform")
        calibration_bins[model_name] = pd.DataFrame(
            {"mean_predicted_risk": mean_pred, "fraction_positive": frac_pos}
        )

    results_df = pd.DataFrame(results).sort_values(
        by=["Recall@Threshold", "F1@Threshold", "Precision@Threshold"],
        ascending=False,
    )
    best_row = pick_best_model(results_df)
    best_model_name = str(best_row["Model"])
    best_model = trained_models[best_model_name]

    print("\nModel comparison:")
    print(results_df.to_string(index=False))
    print(f"\nSelected winner: {best_model_name}")

    importance_df = extract_feature_importance(best_model, feature_columns)

    output_model_path = os.path.join(project_root, "backend", "injury_model.pkl")
    model_bundle = {
        "estimator": best_model,
        "feature_columns": feature_columns,
        "threshold": THRESHOLD,
        "policy": {
            "recall_min": TARGET_RECALL,
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

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_path": dataset_path,
        "dataset_rows": int(len(df)),
        "threshold": THRESHOLD,
        "policy": model_bundle["policy"],
        "winner": best_model_name,
        "winner_metrics": {
            "Recall@Threshold": float(best_row["Recall@Threshold"]),
            "Precision@Threshold": float(best_row["Precision@Threshold"]),
            "F1@Threshold": float(best_row["F1@Threshold"]),
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
    print(f"Saved run manifest: {manifest_path}")


if __name__ == "__main__":
    main()