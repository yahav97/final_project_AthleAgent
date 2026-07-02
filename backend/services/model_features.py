"""
Sklearn feature contract loaded from ``backend/data/model_feature_contract.json``.

The JSON is the single source of truth for:
- ``MODEL_FEATURE_COLUMNS`` — column order passed to ``predict_proba``
- ``DEFAULT_FEATURE_VALUES`` — population defaults when history is thin
- ``TRAINING_CSV_EXCLUDE_COLUMNS`` — columns derived only at serve time
- ``INTEGER_FEATURE_COLUMNS`` — features stored as whole numbers (train + serve)
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

MODEL_FEATURE_CONTRACT_PATH = Path(__file__).resolve().parents[1] / "data" / "model_feature_contract.json"


@lru_cache(maxsize=1)
def load_model_feature_contract() -> dict[str, Any]:
    with MODEL_FEATURE_CONTRACT_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid model feature contract at {MODEL_FEATURE_CONTRACT_PATH}")
    return data


def feature_column_names_from_contract() -> tuple[str, ...]:
    columns = load_model_feature_contract()["feature_columns"]
    if not isinstance(columns, list) or not columns:
        raise ValueError("model_feature_contract.json: feature_columns must be a non-empty list")
    return tuple(str(column) for column in columns)


def default_feature_values_from_contract() -> dict[str, float]:
    defaults = load_model_feature_contract()["default_values"]
    if not isinstance(defaults, dict) or not defaults:
        raise ValueError("model_feature_contract.json: default_values must be a non-empty object")
    return {str(key): float(value) for key, value in defaults.items()}


def training_csv_exclude_columns_from_contract() -> tuple[str, ...]:
    excluded = load_model_feature_contract().get("training_csv_exclude_columns", ())
    if not isinstance(excluded, list):
        raise ValueError("model_feature_contract.json: training_csv_exclude_columns must be a list")
    return tuple(str(column) for column in excluded)


def integer_feature_columns_from_contract() -> tuple[str, ...]:
    columns = load_model_feature_contract().get("integer_feature_columns", ())
    if not isinstance(columns, list):
        raise ValueError("model_feature_contract.json: integer_feature_columns must be a list")
    return tuple(str(column) for column in columns)


def coerce_whole_number_features(features: dict[str, float]) -> dict[str, float]:
    """Round contract integer columns so serve-time values match synthetic training data."""
    out = dict(features)
    for column in INTEGER_FEATURE_COLUMNS:
        if column in out:
            out[column] = float(round(out[column]))
    return out


MODEL_FEATURE_COLUMNS: list[str] = list(feature_column_names_from_contract())
DEFAULT_FEATURE_VALUES: dict[str, float] = default_feature_values_from_contract()
TRAINING_CSV_EXCLUDE_COLUMNS: tuple[str, ...] = training_csv_exclude_columns_from_contract()
INTEGER_FEATURE_COLUMNS: tuple[str, ...] = integer_feature_columns_from_contract()
TRAINING_BASE_FEATURE_COLUMNS: tuple[str, ...] = tuple(
    column for column in MODEL_FEATURE_COLUMNS if column not in TRAINING_CSV_EXCLUDE_COLUMNS
)
