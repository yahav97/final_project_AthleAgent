"""Shared training constants and pipeline dataclasses."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# Model-selection gates: ML_model/policy_config.py (notebook can override live).
# Backend serving gate defaults: backend/config.py → ML_MIN_RECALL_HARD, ML_MIN_AUC_FOR_LIVE.
RANDOM_STATE = 42
DATASET_FILENAME = "athlete_injury_data.csv"
BENCHMARK_FILENAME = "benchmark_holdout.csv"
ATHLETE_CV_SPLITS = 2

# Injury probability cutoffs swept during training (0.10–0.21 step 0.01, then 0.22–0.60 step 0.02).
THRESHOLDS_TO_EVAL = sorted(
    [round(value / 100, 2) for value in range(10, 22)]
    + [round(value / 100, 2) for value in range(22, 62, 2)]
)
LABEL_COLUMN = "injury_today"


@dataclass
class TrainSplit:
    X_train: pd.DataFrame
    X_test: pd.DataFrame
    y_train: pd.Series
    y_test: pd.Series
    y_all: pd.Series
    feature_columns: list[str]
    holdout_athlete_ids: set[int]
    serve_parity_stats: dict[str, object] | None = None


@dataclass
class AthleteCvResult:
    fold_details: pd.DataFrame
    summary: pd.DataFrame


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
    cv_holdout_agreement: dict[str, str | bool | int] | None = None
