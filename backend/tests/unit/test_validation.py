"""Unit tests for model input validation helpers."""

from __future__ import annotations

import pandas as pd
import pytest

from services.preprocessing.validation import (
    ModelServingContract,
    expected_feature_columns,
    parse_model_serving_contract,
    validate_feature_vector_for_model,
)
from utils.exceptions import ValidationError

pytestmark = pytest.mark.unit


class TestModelServingContract:
    def test_parse_dict_contract(self):
        contract = parse_model_serving_contract(
            {"estimator": object(), "feature_columns": ["age", "bmi"]}
        )
        assert contract.feature_columns == ["age", "bmi"]
        assert contract.estimator is not None

    def test_parse_sklearn_estimator(self):
        class _Estimator:
            feature_names_in_ = ["age", "bmi"]

        contract = parse_model_serving_contract(_Estimator())
        assert expected_feature_columns(contract) == ["age", "bmi"]


class TestValidateFeatureVector:
    def test_aligns_and_sanitizes_non_finite_values(self):
        frame = pd.DataFrame([{"age": float("nan"), "bmi": 22.0}])
        aligned = validate_feature_vector_for_model(
            frame,
            {"estimator": object(), "feature_columns": ["age", "bmi"]},
        )
        assert list(aligned.columns) == ["age", "bmi"]
        assert aligned.iloc[0]["age"] == 0.0
        assert aligned.iloc[0]["bmi"] == 22.0

    def test_raises_when_column_missing(self):
        frame = pd.DataFrame([{"age": 28.0}])
        with pytest.raises(ValidationError):
            validate_feature_vector_for_model(
                frame,
                {"estimator": object(), "feature_columns": ["age", "bmi"]},
            )
