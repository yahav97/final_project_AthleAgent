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


def test_profile_fields_override_defaults_when_provided():
    req = InjuryPredictionRequest(age=31, vo2_max=58, history_injury_count=2, sleepMinutes=420)
    df = injury_request_to_model_dataframe(req)
    assert float(df["age"].iloc[0]) == 31.0
    assert float(df["vo2_max"].iloc[0]) == 58.0
    assert float(df["history_injury_count"].iloc[0]) == 2.0
