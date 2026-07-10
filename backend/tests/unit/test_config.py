"""Unit tests for backend Settings defaults."""

from __future__ import annotations

import pytest

from config import Settings, settings

pytestmark = pytest.mark.unit


class TestDomainDefaults:
    def test_profile_default_age(self):
        assert settings.PROFILE_DEFAULT_AGE == 22
        assert settings.PROFILE_DEFAULT_AGE == int(
            __import__("services.model_features", fromlist=["DEFAULT_FEATURE_VALUES"]).DEFAULT_FEATURE_VALUES["age"]
        )

    def test_confidence_blend_weights_sum_to_one(self):
        s = Settings()
        total = s.CONFIDENCE_HISTORY_WEIGHT + s.CONFIDENCE_QUALITY_WEIGHT
        assert total == pytest.approx(1.0)
