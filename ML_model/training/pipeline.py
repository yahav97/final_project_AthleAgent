"""Dataset prep, training loop, CV, artifacts, and end-to-end pipeline."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.metrics import (
    auc,
    brier_score_loss,
    log_loss,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline

from policy_config import get_policy, policy_as_dict
from training.constants import (
    ATHLETE_CV_SPLITS,
    BENCHMARK_RELPATH,
    DATASET_FILENAME,
    LABEL_COLUMN,
    RANDOM_STATE,
    AthleteCvResult,
    TrainResult,
    TrainSplit,
)
from training.models import model_catalog
from training.policy import (
    build_operating_points_table,
    build_risk_bin_table,
    evaluate_with_threshold,
    pick_best_model,
    print_split_diagnostics,
    threshold_sweep,
    winner_operating_threshold,
)
from training.serve_parity import apply_train_serve_parity_augmentation


# --- data & features ---


def _unwrap_sklearn_estimator(model: object) -> object:
    """Reach the fitted estimator inside Pipeline or CalibratedClassifierCV wrappers."""
    if isinstance(model, Pipeline):
        return model.named_steps["model"]
    if isinstance(model, CalibratedClassifierCV):
        calibrated = model.calibrated_classifiers_
        if calibrated and hasattr(calibrated[0], "estimator"):
            return calibrated[0].estimator
    return model


def add_sequential_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add 7-day moving averages of ACWR and sleep (used at serve for history enrichment)."""
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
    base_model = _unwrap_sklearn_estimator(model)
    if hasattr(base_model, "feature_importances_"):
        return pd.DataFrame(
            {"feature": feature_names, "importance": base_model.feature_importances_}
        ).sort_values("importance", ascending=False)
    if hasattr(base_model, "coef_"):
        return pd.DataFrame(
            {"feature": feature_names, "importance": np.abs(base_model.coef_[0])}
        ).sort_values("importance", ascending=False)
    return None


def load_dataset(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    if LABEL_COLUMN not in df.columns:
        raise ValueError(f"Dataset must include '{LABEL_COLUMN}' column: {path}")
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


def prepare_model_frames(
    df: pd.DataFrame,
    *,
    apply_serve_parity: bool = True,
    serve_parity_seed: int = RANDOM_STATE,
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, list[str], dict[str, object]]:
    """Label vector + feature matrix after sequential features and train–serve parity masking."""
    if LABEL_COLUMN not in df.columns:
        raise ValueError(f"Dataset must include '{LABEL_COLUMN}' column.")
    df = add_sequential_features(df)
    df, parity_stats = apply_train_serve_parity_augmentation(
        df,
        seed=serve_parity_seed,
        enabled=apply_serve_parity,
    )
    y = df[LABEL_COLUMN].astype(int)
    model_df = df.drop(columns=[LABEL_COLUMN, "athlete_id", "date"])
    feature_columns = list(model_df.columns)
    return df, y, model_df, feature_columns, parity_stats


def make_train_split(
    df: pd.DataFrame,
    *,
    holdout_ratio: float = 0.2,
    seed: int = RANDOM_STATE,
    benchmark_path: str | Path | None = None,
    apply_serve_parity: bool = True,
    serve_parity_seed: int = RANDOM_STATE,
) -> TrainSplit:
    """Athlete-level holdout split (prefer fixed benchmark CSV athletes when provided)."""
    df, y, model_df, feature_columns, parity_stats = prepare_model_frames(
        df,
        apply_serve_parity=apply_serve_parity,
        serve_parity_seed=serve_parity_seed,
    )
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
        serve_parity_stats=parity_stats,
    )


# --- CV ---


def cross_validate_by_athlete(
    df: pd.DataFrame,
    *,
    n_splits: int = ATHLETE_CV_SPLITS,
    holdout_ratio: float = 0.2,
    base_seed: int = RANDOM_STATE,
    model_names: list[str] | None = None,
    verbose: bool = True,
) -> AthleteCvResult:
    """Repeated random athlete holdouts — stability check before the fixed final split."""
    if n_splits < 1:
        raise ValueError("n_splits must be >= 1")
    catalog = model_catalog()
    if model_names is not None:
        missing = [name for name in model_names if name not in catalog]
        if missing:
            raise ValueError(f"Unknown model names: {missing}")
        catalog = {name: catalog[name] for name in model_names}

    policy = get_policy()
    fold_rows: list[dict[str, float | int | str]] = []
    for fold in range(n_splits):
        seed = base_seed + fold
        split = make_train_split(df, holdout_ratio=holdout_ratio, seed=seed)
        if verbose:
            print(
                f"\nAthlete CV fold {fold + 1}/{n_splits} "
                f"(seed={seed}, holdout_athletes={len(split.holdout_athlete_ids)})"
            )
        for model_name, model in catalog.items():
            if verbose:
                print(f"  Training {model_name}...")
            fitted = clone(model)
            fitted.fit(split.X_train, split.y_train)
            y_proba = fitted.predict_proba(split.X_test)[:, 1]
            metrics = evaluate_with_threshold(split.y_test, y_proba, policy.THRESHOLD)
            pr_precision, pr_recall, _ = precision_recall_curve(split.y_test, y_proba)
            fold_rows.append(
                {
                    "fold": fold + 1,
                    "seed": seed,
                    "Model": model_name,
                    "holdout_athletes": len(split.holdout_athlete_ids),
                    "ROC-AUC": float(roc_auc_score(split.y_test, y_proba)),
                    "PR-AUC": float(auc(pr_recall, pr_precision)),
                    "Recall@Threshold": float(metrics["Recall@Threshold"]),
                    "Precision@Threshold": float(metrics["Precision@Threshold"]),
                    "F1@Threshold": float(metrics["F1@Threshold"]),
                    "FPR@Threshold": float(metrics["FPR@Threshold"]),
                }
            )

    fold_details = pd.DataFrame(fold_rows)
    summary = (
        fold_details.groupby("Model", as_index=False)
        .agg(
            folds=("fold", "count"),
            ROC_AUC_mean=("ROC-AUC", "mean"),
            ROC_AUC_std=("ROC-AUC", "std"),
            Recall_mean=("Recall@Threshold", "mean"),
            Recall_std=("Recall@Threshold", "std"),
            F1_mean=("F1@Threshold", "mean"),
            F1_std=("F1@Threshold", "std"),
            FPR_mean=("FPR@Threshold", "mean"),
            FPR_std=("FPR@Threshold", "std"),
        )
        .sort_values(by=["F1_mean", "Recall_mean", "ROC_AUC_mean"], ascending=[False, False, False])
        .reset_index(drop=True)
    )
    return AthleteCvResult(fold_details=fold_details, summary=summary)


def assess_cv_holdout_agreement(
    cv_result: AthleteCvResult,
    holdout_winner: str,
) -> dict[str, str | bool]:
    """Compare CV stability leader with the holdout winner (informational)."""
    cv_top = str(cv_result.summary.iloc[0]["Model"])
    return {
        "cv_top_model": cv_top,
        "holdout_winner": holdout_winner,
        "agreement": cv_top == holdout_winner,
    }


# --- training ---


def refit_winner_for_serving(df: pd.DataFrame, model_name: str) -> tuple[object, pd.DataFrame | None]:
    """Refit the policy winner on the full dataset for production serving."""
    if model_name not in model_catalog():
        raise ValueError(f"Unknown model: {model_name}")
    _, y, model_df, feature_columns, _parity_stats = prepare_model_frames(df)
    model = clone(model_catalog()[model_name])
    model.fit(model_df, y)
    return model, extract_feature_importance(model, feature_columns)


def train_and_compare(
    split: TrainSplit,
    *,
    model_names: list[str] | None = None,
    cv_result: AthleteCvResult | None = None,
    verbose: bool = True,
) -> TrainResult:
    """Train each catalog model, sweep thresholds, attach operating points + optional CV."""
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

    policy = get_policy()
    for model_name, model in catalog.items():
        if verbose:
            print(f"Training {model_name}...")
        model.fit(split.X_train, split.y_train)
        y_proba = model.predict_proba(split.X_test)[:, 1]
        metrics = evaluate_with_threshold(split.y_test, y_proba, policy.THRESHOLD)
        pr_precision, pr_recall, _ = precision_recall_curve(split.y_test, y_proba)
        pr_auc = auc(pr_recall, pr_precision)
        metrics.update(
            {
                "Model": model_name,
                "ROC-AUC": roc_auc_score(split.y_test, y_proba),
                "PR-AUC": pr_auc,
                "LogLoss": log_loss(split.y_test, y_proba, labels=[0, 1]),
                "BrierScore": brier_score_loss(split.y_test, y_proba),
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
    cv_agreement: dict[str, str | bool | int] | None = None
    if cv_result is not None:
        cv_agreement = assess_cv_holdout_agreement(
            cv_result,
            str(best_row["Model"]),
        )
        if verbose and not cv_agreement.get("agreement"):
            print(
                "\nCV note: top CV model "
                f"({cv_agreement.get('cv_top_model')}) differs from holdout winner "
                f"({cv_agreement.get('holdout_winner')}). Holdout policy stands."
            )
    best_model_name = str(best_row["Model"])
    best_model = trained_models[best_model_name]
    best_operating_threshold = (
        float(best_row["OperatingThreshold"])
        if "OperatingThreshold" in best_row.index
        else winner_operating_threshold(threshold_rows, best_model_name)
    )
    winner_proba = best_model.predict_proba(split.X_test)[:, 1]
    winner_operating_metrics = evaluate_with_threshold(
        split.y_test, winner_proba, best_operating_threshold
    )
    risk_bins_df = build_risk_bin_table(split.y_test, winner_proba)
    importance_df = extract_feature_importance(best_model, split.feature_columns)
    best_points = build_operating_points_table(results_df, threshold_rows)

    return TrainResult(
        results_df=results_df,
        threshold_rows=threshold_rows,
        calibration_bins=calibration_bins,
        best_row=best_row,
        best_model_name=best_model_name,
        best_model=best_model,
        best_operating_threshold=best_operating_threshold,
        winner_operating_metrics=winner_operating_metrics,
        risk_bins_df=risk_bins_df,
        importance_df=importance_df,
        best_points=best_points,
        cv_holdout_agreement=cv_agreement,
    )


# --- artifacts ---


def _project_relative_path(path: Path, project_root: Path) -> str:
    return path.resolve().relative_to(project_root.resolve()).as_posix()


def save_training_artifacts(
    result: TrainResult,
    split: TrainSplit,
    *,
    artifacts_dir: str | Path,
    dataset_path: str | Path,
    project_root: str | Path,
    benchmark_path: str | Path | None = None,
    dataset_rows: int | None = None,
    cv_result: AthleteCvResult | None = None,
    serving_estimator: object | None = None,
    serving_importance_df: pd.DataFrame | None = None,
    cv_agreement: dict[str, str | bool] | None = None,
    serve_parity_stats: dict[str, object] | None = None,
) -> Path:
    """Write CSV metrics, run_manifest.json, and injury_model.pkl for this training run."""
    artifacts_dir = Path(artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    run_id = artifacts_dir.name
    output_model_path = artifacts_dir / "injury_model.pkl"
    estimator_for_serving = serving_estimator if serving_estimator is not None else result.best_model
    model_bundle = {
        "estimator": estimator_for_serving,
        "feature_columns": split.feature_columns,
        "threshold": result.best_operating_threshold,
        "policy": policy_as_dict(),
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
        "artifacts_dir": _project_relative_path(artifacts_dir, project_root),
        "dataset_path": _project_relative_path(Path(dataset_path), project_root),
        "dataset_rows": int(dataset_rows if dataset_rows is not None else len(split.y_all)),
        "benchmark_path": (
            _project_relative_path(Path(benchmark_path), project_root)
            if benchmark_path and Path(benchmark_path).is_file()
            else None
        ),
        "threshold": result.best_operating_threshold,
        "policy": model_bundle["policy"],
        "winner": result.best_model_name,
        "selection_protocol": {
            "athlete_cv_splits": ATHLETE_CV_SPLITS if cv_result is not None else None,
            "metrics_source": "fixed_holdout_evaluation",
            "serving_model_fit": "full_dataset_refit" if serving_estimator is not None else "holdout_train_only",
            "cv_holdout_agreement": cv_agreement,
            "train_serve_parity_augmentation": serve_parity_stats,
        },
        "winner_metrics": {
            "Recall@Threshold": float(result.winner_operating_metrics["Recall@Threshold"]),
            "Precision@Threshold": float(result.winner_operating_metrics["Precision@Threshold"]),
            "F1@Threshold": float(result.winner_operating_metrics["F1@Threshold"]),
            "FPR@Threshold": float(result.winner_operating_metrics["FPR@Threshold"]),
            "BrierScore": float(result.best_row["BrierScore"]),
            "ROC-AUC": float(result.best_row["ROC-AUC"]),
            "LogLoss": float(result.best_row["LogLoss"]),
        },
    }
    manifest_path = artifacts_dir / "run_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # Prefer full-data refit importance when available (matches the served estimator).
    importance_to_save = serving_importance_df if serving_importance_df is not None else result.importance_df
    if importance_to_save is not None:
        importance_to_save.to_csv(artifacts_dir / "feature_importance.csv", index=False)
    if cv_result is not None:
        cv_result.fold_details.to_csv(artifacts_dir / "athlete_cv_folds.csv", index=False)
        cv_result.summary.to_csv(artifacts_dir / "athlete_cv_summary.csv", index=False)

    return artifacts_dir


# --- orchestration ---


def run_training_pipeline(
    *,
    ml_dir: str | Path | None = None,
    verbose: bool = True,
) -> Path:
    """Full training flow: athlete CV → holdout selection → refit → artifacts."""
    ml_dir = Path(ml_dir or Path(__file__).resolve().parent.parent)
    project_root = ml_dir.parent
    dataset_path = ml_dir / DATASET_FILENAME
    benchmark_path = ml_dir / BENCHMARK_RELPATH
    if not dataset_path.is_file():
        raise FileNotFoundError(f"{dataset_path} not found. Run data_generator.py first.")
    benchmark_file = benchmark_path if benchmark_path.is_file() else None

    df = load_dataset(dataset_path)
    if verbose:
        print(f"Training dataset: {dataset_path} ({len(df):,} rows)")
        print(f"Athlete CV stability check ({ATHLETE_CV_SPLITS} random holdouts)...")
    cv_result = cross_validate_by_athlete(df, base_seed=RANDOM_STATE, verbose=verbose)
    if verbose:
        print("\nAthlete CV summary (mean ± std @ policy threshold):")
        print(cv_result.summary.to_string(index=False))

    split = make_train_split(df, benchmark_path=benchmark_file, seed=RANDOM_STATE)
    serve_parity_stats = split.serve_parity_stats or {}
    if verbose and serve_parity_stats.get("enabled"):
        print(
            "\nTrain-serve parity augmentation: "
            f"cold_start={serve_parity_stats.get('cold_start_rows'):,} rows "
            f"({serve_parity_stats.get('cold_start_fraction_actual', 0):.1%}), "
            f"nutrition_masked={serve_parity_stats.get('nutrition_mask_rows'):,} rows "
            f"({serve_parity_stats.get('nutrition_mask_fraction_actual', 0):.1%})"
        )
    if verbose:
        print("\nFinal model selection on fixed benchmark holdout...")
    result = train_and_compare(split, cv_result=cv_result, verbose=verbose)

    cv_agreement = result.cv_holdout_agreement or assess_cv_holdout_agreement(
        cv_result,
        result.best_model_name,
    )
    if verbose:
        if cv_agreement["agreement"]:
            print(
                f"\nCV stability: top CV model ({cv_agreement['cv_top_model']}) "
                f"matches holdout winner."
            )
        else:
            print(
                f"\nCV note: top CV model ({cv_agreement['cv_top_model']}) "
                f"differs from holdout winner ({cv_agreement['holdout_winner']})."
            )
        print(f"\nRefitting {result.best_model_name} on full dataset for serving...")
    serving_model, serving_importance = refit_winner_for_serving(df, result.best_model_name)

    if verbose:
        print("\nModel comparison:")
        print(result.results_df.to_string(index=False))
        print("\nThreshold sweep summary:")
        print(pd.DataFrame(result.threshold_rows).sort_values(by=["Model", "Threshold"]).to_string(index=False))
        print("\nBest operating points per model (tiered policy):")
        print(result.best_points.to_string(index=False))
        print(f"\nSelected winner: {result.best_model_name}")
        print(
            f"  @ threshold {result.best_operating_threshold:.2f}: "
            f"Recall={result.winner_operating_metrics['Recall@Threshold']:.3f}, "
            f"Precision={result.winner_operating_metrics['Precision@Threshold']:.3f}, "
            f"F1={result.winner_operating_metrics['F1@Threshold']:.3f}, "
            f"FPR={result.winner_operating_metrics['FPR@Threshold']:.3f}"
        )

    out_dir = ml_dir / "artifacts" / datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    save_training_artifacts(
        result,
        split,
        artifacts_dir=out_dir,
        dataset_path=dataset_path,
        project_root=project_root,
        benchmark_path=benchmark_file,
        dataset_rows=len(df),
        cv_result=cv_result,
        serving_estimator=serving_model,
        serving_importance_df=serving_importance,
        cv_agreement=cv_agreement,
        serve_parity_stats=split.serve_parity_stats,
    )

    if verbose:
        print(f"\nSaved model bundle: {out_dir / 'injury_model.pkl'}")
        print(f"Saved comparison: {out_dir / 'model_comparison.csv'}")
        print(f"Saved calibration data: {out_dir / 'calibration_curve_data.csv'}")
        print(f"Saved threshold sweep: {out_dir / 'threshold_sweep.csv'}")
        print(f"Saved best operating points: {out_dir / 'best_operating_points.csv'}")
        print(f"Saved risk bins summary: {out_dir / 'risk_bins_summary.csv'}")
        print(f"Saved run manifest: {out_dir / 'run_manifest.json'}")
    return out_dir
