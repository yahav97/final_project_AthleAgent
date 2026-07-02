"""Load shared sklearn feature contract from backend/data/model_feature_contract.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

CONTRACT_PATH = (
    Path(__file__).resolve().parents[1] / "backend" / "data" / "model_feature_contract.json"
)


def load_feature_contract() -> dict[str, Any]:
    with CONTRACT_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid feature contract at {CONTRACT_PATH}")
    return data


def integer_feature_columns() -> tuple[str, ...]:
    columns = load_feature_contract().get("integer_feature_columns", ())
    if not isinstance(columns, list):
        raise ValueError("model_feature_contract.json: integer_feature_columns must be a list")
    return tuple(str(column) for column in columns)


def workout_intensity_minutes(daily_distance_km: float, active_calories: float) -> int:
    """Match backend/services/preprocessing/request_features.py."""
    if daily_distance_km <= 0.2:
        return 0
    return int(round(daily_distance_km * 5.5 + active_calories / 40.0))


def normalize_whole_number_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Round integer contract columns to whole numbers (sklearn still receives float64)."""
    out = df.copy()
    for column in integer_feature_columns():
        if column in out.columns:
            out[column] = out[column].round().astype(float)
    return out


def assert_whole_number_columns(df: pd.DataFrame) -> None:
    """Raise when integer contract columns contain fractional values."""
    for column in integer_feature_columns():
        if column not in df.columns:
            continue
        series = pd.to_numeric(df[column], errors="coerce").dropna()
        if series.empty:
            continue
        remainder = np.abs(series % 1.0)
        if (remainder > 1e-9).any():
            bad = int((remainder > 1e-9).sum())
            raise ValueError(f"{column}: {bad} non-integer values in synthetic dataset")


def assert_finite_feature_columns(df: pd.DataFrame, columns: tuple[str, ...] | list[str]) -> None:
    """Raise when model feature columns contain NaN or non-finite values."""
    for column in columns:
        if column not in df.columns:
            continue
        series = pd.to_numeric(df[column], errors="coerce")
        if not np.isfinite(series.to_numpy(dtype=float)).all():
            raise ValueError(f"{column}: non-finite values in synthetic dataset")
