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
THRESHOLDS_TO_EVAL = sorted(
    {
        round(x, 2)
        for x in list(np.arange(0.10, 0.22, 0.01)) + list(np.arange(0.22, 0.62, 0.02))
    }
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
