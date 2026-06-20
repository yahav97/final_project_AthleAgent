"""Unit tests for production risk band classification."""

import pytest

from services.risk_levels import classify_risk_level


@pytest.mark.parametrize(
    ("probability", "expected"),
    [
        (0.0, "Low"),
        (0.20, "Low"),
        (0.205, "Low"),  # int(20.5) == 20 → green on Android
        (0.21, "Medium"),
        (0.50, "Medium"),
        (0.70, "Medium"),  # int(70) == 70 → orange on Android
        (0.706, "Medium"),  # int(70.6) == 70
        (0.71, "High"),
        (0.99, "High"),
    ],
)
def test_classify_risk_level_matches_android_bands(probability, expected):
    assert classify_risk_level(probability) == expected
