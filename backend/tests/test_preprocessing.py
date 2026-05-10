import math

import pandas as pd

from schemas.inference import InjuryPredictionRequest
from services.model_features import MODEL_FEATURE_COLUMNS
from services.preprocessing import calculate_data_quality_score, injury_request_to_model_dataframe


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


def test_nutrition_intake_overrides_default_when_provided():
    req = InjuryPredictionRequest(sleepMinutes=420, nutritionTotalCalories=3100.0)
    df = injury_request_to_model_dataframe(req)
    assert float(df["nutrition_intake_calories"].iloc[0]) == 3100.0


def test_age_and_history_injury_from_profile_when_provided():
    req = InjuryPredictionRequest(sleepMinutes=420, age=31, historyInjuryCount=2)
    df = injury_request_to_model_dataframe(req)
    assert float(df["age"].iloc[0]) == 31.0
    assert float(df["history_injury_count"].iloc[0]) == 2.0


def test_quality_score_tolerates_missing_nutrition_fields():
    req = InjuryPredictionRequest(
        userId="u1",
        date="2026-04-27",
        sleepMinutes=420,
        steps=9000,
        stressLevel=40,
        muscleSoreness=3,
    )
    q = calculate_data_quality_score(req)
    assert q["has_hard_blocker"] is False
    assert float(q["score"]) > 0.5
    assert "totalProtein" not in q["sensitive_missing"]


def test_quality_score_sets_hard_blocker_without_load_signal():
    req = InjuryPredictionRequest(
        userId="u1",
        date="2026-04-27",
        sleepMinutes=420,
        stressLevel=40,
        muscleSoreness=3,
    )
    q = calculate_data_quality_score(req)
    assert q["has_hard_blocker"] is True
    assert "load_signal" in q["hard_missing"]
