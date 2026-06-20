"""Unit tests for shared Firestore / API field transforms."""

from __future__ import annotations

import pytest

from services import history_service as hs
from services.field_transforms import (
    daily_distance_km,
    daily_distance_km_from_doc,
    injured_yesterday_as_feature,
    injured_yesterday_for_request,
    injured_yesterday_from_doc,
    resting_hr,
    resting_hr_from_doc,
)
from services.model_features import DEFAULT_FEATURE_VALUES

pytestmark = pytest.mark.unit


class TestDailyDistanceKm:
    def test_prefers_distance_meters(self):
        assert daily_distance_km(5000, 10000) == pytest.approx(5.0)
        assert daily_distance_km_from_doc({"distanceMeters": 5000, "steps": 10000}) == pytest.approx(5.0)

    def test_steps_fallback_when_no_distance(self):
        assert daily_distance_km(0, 10000) == pytest.approx(8.0)

    def test_zero_when_no_signals(self):
        assert daily_distance_km_from_doc({}) == pytest.approx(0.0)


class TestRestingHr:
    def test_priority_chain(self):
        assert resting_hr_from_doc({"restingHeartRate": 48}) == pytest.approx(48.0)
        assert resting_hr_from_doc({"heartRateMin": 50}) == pytest.approx(50.0)
        assert resting_hr_from_doc({"heartRateAvg": 60}) == pytest.approx(60.0)
        assert resting_hr_from_doc({}) == pytest.approx(54.0)

    def test_clamps_extreme_values(self):
        assert resting_hr(20, 0, 0) == pytest.approx(38.0)
        assert resting_hr(120, 0, 0) == pytest.approx(95.0)


class TestInjuredYesterday:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [(None, DEFAULT_FEATURE_VALUES["injured_yesterday"]), (True, 1.0), (False, 0.0), (0, 0.0), (1, 1.0)],
    )
    def test_injured_yesterday_as_feature(self, raw, expected):
        assert injured_yesterday_as_feature(raw) == pytest.approx(expected)

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [(True, 1), (False, 0), (1, 1), (0, 0), (None, None), ("bad", None)],
    )
    def test_injured_yesterday_for_request(self, raw, expected):
        assert injured_yesterday_for_request(raw) == expected

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [(True, 1), (False, 0), (1, 1), (0, 0), (None, None)],
    )
    def test_injured_yesterday_from_doc(self, raw, expected):
        doc = {} if raw is None else {"injuredYesterday": raw}
        assert injured_yesterday_from_doc(doc) == expected


class TestHrvScore:
    def test_uses_rmssd_when_present(self):
        doc = {"hrvRmssd": 72.0, "heartRateAvg": 60}
        assert hs._hrv_score(doc, resting_hr=54.0) == pytest.approx(72.0)

    def test_falls_back_to_proxy(self):
        doc = {"heartRateAvg": 60}
        assert hs._hrv_score(doc, resting_hr=54.0) == pytest.approx(74.9, rel=0.01)

    def test_historical_hrv_drop_uses_real_hrv_series(self):
        rows = [
            {"date_key": "2026-05-01", "hrvRmssd": 60.0, "distanceMeters": 1000, "sleepMinutes": 420},
            {"date_key": "2026-05-02", "hrvRmssd": 60.0, "distanceMeters": 1000, "sleepMinutes": 420},
            {"date_key": "2026-05-03", "hrvRmssd": 45.0, "distanceMeters": 1000, "sleepMinutes": 420},
        ]
        out = hs.compute_historical_derived_features(rows)
        assert out is not None
        assert out["hrv_drop"] == pytest.approx(-10.0)
