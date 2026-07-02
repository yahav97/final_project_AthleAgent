"""Contract tests: serving rolling features align with training semantics."""

from __future__ import annotations

import pandas as pd
import pytest

from services.feature_engineering import compute_derived_features
from services.history.rolling_features import (
    compute_historical_derived_features,
    sleep_hours_from_doc,
)
from services.preprocessing.request_features import add_same_day_composite_features

pytestmark = pytest.mark.unit


def _training_style_ma7(acwr_values: list[float], sleep_values: list[float]) -> tuple[float, float]:
    """Mirror ML_model/train_model.add_sequential_features rolling means."""
    frame = pd.DataFrame({"acwr_ratio": acwr_values, "sleep_hours": sleep_values})
    acwr_ma7 = float(frame["acwr_ratio"].rolling(7, min_periods=1).mean().iloc[-1])
    sleep_ma7 = float(frame["sleep_hours"].rolling(7, min_periods=1).mean().iloc[-1])
    return acwr_ma7, sleep_ma7


class TestRollingMa7Parity:
    def test_serving_ma7_matches_training_rolling_mean_on_history(self):
        rows = [
            {
                "date_key": f"2026-05-{day:02d}",
                "distanceMeters": 4000 + day * 250,
                "sleepMinutes": 360 + day * 15,
                "hrvRmssd": 58.0,
                "heartRateAvg": 56,
                "activeCalories": 380 + day * 12,
            }
            for day in range(1, 8)
        ]
        served = compute_historical_derived_features(rows)
        assert served is not None

        acwr_series: list[float] = []
        sleep_series: list[float] = []
        for index in range(1, len(rows) + 1):
            partial = compute_historical_derived_features(rows[:index])
            assert partial is not None
            acwr_series.append(partial["acwr_ratio"])
            sleep_series.append(sleep_hours_from_doc(rows[index - 1]))

        expected_acwr_ma7, expected_sleep_ma7 = _training_style_ma7(acwr_series, sleep_series)
        assert served["acwr_ratio_ma7"] == pytest.approx(expected_acwr_ma7, rel=1e-6)
        assert served["sleep_hours_ma7"] == pytest.approx(expected_sleep_ma7, rel=1e-6)

    def test_same_day_proxy_used_before_history_enrichment(self):
        base = {
            "daily_distance_km": 6.0,
            "sleep_hours": 7.5,
            "active_calories_burned": 500.0,
            "bmr_calories": 1600.0,
            "hrv_score": 65.0,
            "resting_hr": 52.0,
            "total_calories_burned": 2100.0,
            "daily_calories": 2200.0,
            "max_speed": 12.0,
            "avg_speed": 8.0,
        }
        derived = {**base, **compute_derived_features(base)}
        composite = add_same_day_composite_features(derived)
        assert composite["acwr_ratio_ma7"] == pytest.approx(composite["acwr_ratio"])
        assert composite["sleep_hours_ma7"] == pytest.approx(composite["sleep_hours"])
