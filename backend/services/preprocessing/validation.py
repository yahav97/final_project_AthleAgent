"""Validate model input rows against the training column contract."""

from __future__ import annotations

from typing import NamedTuple

import numpy as np
import pandas as pd

from utils.exceptions import ValidationError
from utils.logging import logger


class ModelServingContract(NamedTuple):
    """Estimator plus optional explicit feature column list from the joblib bundle."""

    estimator: object | None
    feature_columns: list[str] | None


def parse_model_serving_contract(model: object | None) -> ModelServingContract:
    """
    Accept either a sklearn estimator or the dict passed from ``prediction.service``:

    ``{"estimator": <model>, "feature_columns": [...]}``
    """
    if isinstance(model, dict):
        columns = model.get("feature_columns")
        feature_columns = (
            [str(column) for column in columns]
            if isinstance(columns, list) and columns
            else None
        )
        return ModelServingContract(model.get("estimator"), feature_columns)

    return ModelServingContract(model, None)


def expected_feature_columns(contract: ModelServingContract) -> list[str] | None:
    """Resolve column order from bundle dict or ``estimator.feature_names_in_``."""
    if contract.feature_columns:
        return contract.feature_columns

    feature_names = getattr(contract.estimator, "feature_names_in_", None)
    if feature_names is not None:
        return [str(column) for column in feature_names]
    return None


def align_dataframe_to_columns(frame: pd.DataFrame, column_names: list[str]) -> pd.DataFrame:
    missing = [column for column in column_names if column not in frame.columns]
    if missing:
        raise ValidationError(f"Model expects missing feature columns: {missing}")
    return frame.loc[:, column_names]


def coerce_finite_float_row(frame: pd.DataFrame) -> pd.DataFrame:
    """Cast to float64 and replace NaN / non-finite values with 0.0."""
    aligned = frame.astype("float64").fillna(0.0)
    values = aligned.to_numpy(dtype="float64", copy=True)
    bad_mask = ~np.isfinite(values)
    if bad_mask.any():
        logger.warning(
            "feature_vector_coerced_non_finite count=%d",
            int(bad_mask.sum()),
            extra={"event": "feature_vector_coerced_non_finite"},
        )
    values[bad_mask] = 0.0
    return pd.DataFrame(values, columns=aligned.columns, index=aligned.index, dtype="float64")


def validate_feature_vector_for_model(
    frame: pd.DataFrame,
    model: object | None,
) -> pd.DataFrame:
    """
    Align final model input to the training column contract.

    Ensures:
    - expected columns exist and are ordered exactly like training
    - NaN and non-finite values are coerced to 0.0 (confidence is handled upstream)
    """
    contract = parse_model_serving_contract(model)
    column_names = expected_feature_columns(contract)
    aligned = align_dataframe_to_columns(frame, column_names) if column_names else frame
    return coerce_finite_float_row(aligned)
