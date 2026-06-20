"""Feature column contract for injury_model.pkl (loaded from disk, cached in memory)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_CONTRACT_PATH = Path(__file__).resolve().parents[1] / "data" / "model_feature_contract.json"


@lru_cache(maxsize=1)
def _load_contract() -> dict[str, Any]:
    with _CONTRACT_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid model feature contract at {_CONTRACT_PATH}")
    return data


def _feature_columns() -> tuple[str, ...]:
    columns = _load_contract()["feature_columns"]
    if not isinstance(columns, list) or not columns:
        raise ValueError("model_feature_contract.json: feature_columns must be a non-empty list")
    return tuple(str(column) for column in columns)


def _default_values() -> dict[str, float]:
    defaults = _load_contract()["default_values"]
    if not isinstance(defaults, dict) or not defaults:
        raise ValueError("model_feature_contract.json: default_values must be a non-empty object")
    return {str(key): float(value) for key, value in defaults.items()}


def _training_csv_exclude_columns() -> tuple[str, ...]:
    excluded = _load_contract().get("training_csv_exclude_columns", ())
    if not isinstance(excluded, list):
        raise ValueError("model_feature_contract.json: training_csv_exclude_columns must be a list")
    return tuple(str(column) for column in excluded)


MODEL_FEATURE_COLUMNS: list[str] = list(_feature_columns())
DEFAULT_FEATURE_VALUES: dict[str, float] = _default_values()
TRAINING_CSV_EXCLUDE_COLUMNS: tuple[str, ...] = _training_csv_exclude_columns()
TRAINING_BASE_FEATURE_COLUMNS: tuple[str, ...] = tuple(
    column for column in MODEL_FEATURE_COLUMNS if column not in TRAINING_CSV_EXCLUDE_COLUMNS
)
