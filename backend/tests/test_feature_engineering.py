import pytest

from services.feature_engineering import compute_derived_features


def test_acwr_ratio_bounded():
    row = {
        "daily_distance_km": 12.0,
        "_active_calories": 800.0,
        "sleep_hours": 6.0,
        "hrv_score": 55.0,
        "resting_hr": 58.0,
    }
    out = compute_derived_features(row)
    assert 0.35 <= out["acwr_ratio"] <= 2.8
    assert out["acute_load_7d"] > 0
    assert out["chronic_load_21d"] > 0
    raw_ratio = out["acute_load_7d"] / out["chronic_load_21d"]
    expected = min(2.8, max(0.35, raw_ratio))
    assert out["acwr_ratio"] == pytest.approx(expected)


def test_rest_day_low_acute():
    row = {
        "daily_distance_km": 0.0,
        "_active_calories": 0.0,
        "sleep_hours": 8.5,
        "hrv_score": 65.0,
        "resting_hr": 52.0,
    }
    out = compute_derived_features(row)
    assert out["acute_load_7d"] >= 0.05
    assert out["sleep_debt_3d"] == 0.0
