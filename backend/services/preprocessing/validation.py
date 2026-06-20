"""Validate model input rows against the training contract."""

from __future__ import annotations

import math

import pandas as pd

from utils.exceptions import ValidationError


def validate_feature_vector_for_model(df: pd.DataFrame, model: object | None) -> pd.DataFrame:
    """
    Validate final model input against training contract.

    Ensures:
    - expected columns exist and are ordered exactly like training
    - all values are finite float64
    - critical scaled ranges remain in sane model bounds
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

    aligned = df.astype("float64")
    if not pd.Series(pd.notna(aligned.to_numpy().ravel())).all():
        raise ValidationError("Feature vector contains NaN values")
    if not pd.Series(pd.Series(aligned.to_numpy().ravel()).map(math.isfinite)).all():
        raise ValidationError("Feature vector contains non-finite values")

    range_checks: tuple[tuple[str, float, float], ...] = (
        ("stress_level", 1.0, 10.0),
        ("muscle_soreness", 1.0, 10.0),
        ("energy_level", 1.0, 10.0),
        ("injured_yesterday", 0.0, 1.0),
        ("age", 12.0, 90.0),
        ("history_injury_count", 0.0, 50.0),
        ("nutrition_intake_calories", 0.0, 8000.0),
        ("acwr_ratio", 0.35, 2.8),
    )
    for column, lower, upper in range_checks:
        if column not in aligned.columns:
            continue
        value = float(aligned[column].iloc[0])
        if value < lower or value > upper:
            raise ValidationError(f"{column} out of expected range [{lower},{upper}]: {value}")
    return aligned
