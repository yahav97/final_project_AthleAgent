"""Map InjuryPredictionRequest to a single model-ready DataFrame row."""

from __future__ import annotations

import math
from typing import Any, cast

import pandas as pd

from schemas.inference import InjuryPredictionRequest
from services.feature_engineering import compute_derived_features
from services.model_features import MODEL_FEATURE_COLUMNS, coerce_whole_number_features
from services.preprocessing.request_features import (
    add_same_day_composite_features,
    base_model_features_from_request,
)


def injury_request_to_model_dataframe(payload: InjuryPredictionRequest) -> pd.DataFrame:
    """
    Build one model-ready row: Android-shaped request → engineered DataFrame.

    Policy:
    - Trust frontend payloads; no range clamping on received values.
    - Missing / NaN numeric inputs become 0.0 (confidence handled separately).
    - Survey fields use fixed scale mapping (see ``scales``).
    - Historical rolling features are enriched later in ``confidence`` module.
    """
    payload_dict = payload.model_dump()

    features = base_model_features_from_request(payload_dict)
    features.update(compute_derived_features(features))
    features = add_same_day_composite_features(features)
    features = coerce_whole_number_features(features)

    row: dict[str, float] = {}
    for column in MODEL_FEATURE_COLUMNS:
        value = features.get(column)
        if value is None or (isinstance(value, float) and not math.isfinite(value)):
            value = 0.0
        row[column] = float(value)

    feature_columns = list(MODEL_FEATURE_COLUMNS)
    frame = pd.DataFrame([row], columns=cast(Any, feature_columns))
    return frame.astype("float64").fillna(0.0)
