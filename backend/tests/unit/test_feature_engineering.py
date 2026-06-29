import pytest

from services.feature_engineering import (
    acwr_baseline_from_acute_proxy,
    acwr_ratio_bounded,
    compute_derived_features,
)

pytestmark = pytest.mark.unit


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
    baseline = acwr_baseline_from_acute_proxy(out["acute_load_7d"])
    assert out["acwr_ratio"] == pytest.approx(acwr_ratio_bounded(out["acute_load_7d"], baseline))
    assert "chronic_load_7d" not in out


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
