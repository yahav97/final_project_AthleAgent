"""Validate model input rows against the training contract."""

from __future__ import annotations

import math

import pandas as pd

from utils.exceptions import ValidationError


def validate_feature_vector_for_model(df: pd.DataFrame, model: object | None) -> pd.DataFrame:
    """
    Align final model input to the training column contract.

    Ensures:
    - expected columns exist and are ordered exactly like training
    - NaN and non-finite values are coerced to 0.0 (confidence is handled upstream)
  """
    expected_columns = None
    if isinstance(model, dict):
        columns = model.get("feature_columns")
        if isinstance(columns, list) and columns:
            expected_columns = [str(column) for column in columns]
        model = model.get("estimator")
    if expected_columns is None:
        feature_names = getattr(model, "feature_names_in_", None)
        if feature_names is not None:
            expected_columns = [str(column) for column in feature_names]
    if expected_columns:
        missing = [column for column in expected_columns if column not in df.columns]
        if missing:
            raise ValidationError(f"Model expects missing feature columns: {missing}")
        df = df.loc[:, expected_columns]

    aligned = df.astype("float64").fillna(0.0)
    values = aligned.to_numpy().ravel()
    sanitized = [0.0 if not math.isfinite(float(v)) else float(v) for v in values]
    return pd.DataFrame([sanitized], columns=aligned.columns, dtype="float64")
