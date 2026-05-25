import pytest

from services.history_service import (
    _hrv_score,
    _resting_hr,
    compute_historical_derived_features,
)


def test_resting_hr_prefers_resting_heart_rate():
    doc = {"restingHeartRate": 48, "heartRateMin": 55, "heartRateAvg": 60}
    assert _resting_hr(doc) == pytest.approx(48.0)


def test_hrv_score_uses_rmssd_when_present():
    doc = {"hrvRmssd": 72.0, "heartRateAvg": 60}
    assert _hrv_score(doc, resting_hr=54.0) == pytest.approx(72.0)


def test_hrv_score_falls_back_to_proxy():
    doc = {"heartRateAvg": 60}
    assert _hrv_score(doc, resting_hr=54.0) == pytest.approx(74.9, rel=0.01)


def test_historical_hrv_drop_uses_real_hrv_series():
    rows = [
        {"date_key": "2026-05-01", "hrvRmssd": 60.0, "distanceMeters": 1000, "sleepMinutes": 420},
        {"date_key": "2026-05-02", "hrvRmssd": 60.0, "distanceMeters": 1000, "sleepMinutes": 420},
        {"date_key": "2026-05-03", "hrvRmssd": 45.0, "distanceMeters": 1000, "sleepMinutes": 420},
    ]
    out = compute_historical_derived_features(rows)
    assert out is not None
    # day 3: 45 − mean(60, 60, 45) = −10
    assert out["hrv_drop"] == pytest.approx(-10.0)
