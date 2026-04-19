import math

import pandas as pd

from schemas.inference import InjuryPredictionRequest
from services.model_features import MODEL_FEATURE_COLUMNS
from services.preprocessing import injury_request_to_model_dataframe


def test_dataframe_shape_and_no_nan():
    req = InjuryPredictionRequest(
        sleepMinutes=360,
        steps=12000,
        distanceMeters=8000,
        activeCalories=600,
        totalCalories=2800,
        stressLevel=75,
        muscleSoreness=3,
    )
    df = injury_request_to_model_dataframe(req)
    assert list(df.columns) == MODEL_FEATURE_COLUMNS
    assert df.shape == (1, len(MODEL_FEATURE_COLUMNS))
    assert not df.isna().any().any()
    assert all(math.isfinite(x) for x in df.iloc[0].tolist())


def test_stress_mapping_from_0_100_scale():
    req = InjuryPredictionRequest(stressLevel=80, sleepMinutes=480)
    df = injury_request_to_model_dataframe(req)
    assert 1 <= df["stress_level"].iloc[0] <= 10


def test_types_float64():
    req = InjuryPredictionRequest()
    df = injury_request_to_model_dataframe(req)
    assert df.dtypes.apply(lambda t: pd.api.types.is_float_dtype(t)).all()
