import pytest

from config import settings
from services.feature_engineering import (
    acwr_baseline_from_acute_proxy,
    acwr_ratio_bounded,
    compute_derived_features,
    daily_sleep_deficit_hours,
    sleep_debt_3d_from_sleep_hours,
)

pytestmark = pytest.mark.unit


def test_acwr_ratio_bounded():
    row = {
        "daily_distance_km": 12.0,
        "active_calories_burned": 800.0,
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
        "active_calories_burned": 0.0,
        "sleep_hours": 8.5,
        "hrv_score": 65.0,
        "resting_hr": 52.0,
    }
    out = compute_derived_features(row)
    assert out["acute_load_7d"] >= 0.05
    assert out["sleep_debt_3d"] == 0.0


def test_acwr_ratio_bounded_caps_at_upper_and_lower_limits():
    assert acwr_ratio_bounded(100.0, 1.0) == pytest.approx(2.8)
    assert acwr_ratio_bounded(0.1, 1.0) == pytest.approx(0.35)


def test_zero_sleep_increases_sleep_debt_proxy():
    row = {
        "daily_distance_km": 10.0,
        "active_calories_burned": 600.0,
        "sleep_hours": 0.0,
        "hrv_score": 55.0,
        "resting_hr": 58.0,
    }
    out = compute_derived_features(row)
    # Missing sleep is treated as 7h default before debt calc → 1h deficit vs 8h target.
    assert out["sleep_debt_3d"] == pytest.approx(1.0)


def test_sleep_debt_3d_matches_training_rolling_formula():
    target = settings.SLEEP_TARGET_HOURS
    # 3 nights: 6h, 7h, 9h → deficits 2 + 1 + 0 = 3
    assert sleep_debt_3d_from_sleep_hours([6.0, 7.0, 9.0], sleep_target=target) == pytest.approx(3.0)
    # Oversleep does not create negative debt.
    assert sleep_debt_3d_from_sleep_hours([9.0, 9.0, 9.0], sleep_target=target) == pytest.approx(0.0)
    # min_periods=1 with a single day.
    assert sleep_debt_3d_from_sleep_hours([6.0], sleep_target=target) == pytest.approx(2.0)


def test_daily_sleep_deficit_clips_oversleep():
    assert daily_sleep_deficit_hours(9.0, sleep_target=8.0) == pytest.approx(0.0)
    assert daily_sleep_deficit_hours(6.0, sleep_target=8.0) == pytest.approx(2.0)


def test_single_day_sleep_debt_uses_training_formula_not_scaled_proxy():
    row = {
        "daily_distance_km": 5.0,
        "active_calories_burned": 300.0,
        "sleep_hours": 6.0,
        "hrv_score": 60.0,
        "resting_hr": 54.0,
    }
    out = compute_derived_features(row)
    assert out["sleep_debt_3d"] == pytest.approx(2.0)


def test_acwr_ratio_returns_one_when_baseline_non_positive():
    assert acwr_ratio_bounded(1.0, 0.0) == 1.0
