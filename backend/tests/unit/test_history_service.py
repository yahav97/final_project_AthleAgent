"""Unit tests for history_service rolling features and helpers."""

from __future__ import annotations

import pytest

from services import history_service as hs

pytestmark = pytest.mark.unit


class TestStableAthleteId:
    def test_deterministic_for_same_uid(self):
        assert hs.stable_athlete_numeric_id("firebase-uid-abc") == hs.stable_athlete_numeric_id(
            "firebase-uid-abc"
        )

    def test_different_uids_produce_different_ids(self):
        a = hs.stable_athlete_numeric_id("athlete-a")
        b = hs.stable_athlete_numeric_id("athlete-b")
        assert a != b

    def test_always_positive(self):
        assert hs.stable_athlete_numeric_id("") > 0


class TestDailyDistanceKm:
    def test_prefers_distance_meters(self):
        assert hs._daily_distance_km({"distanceMeters": 5000, "steps": 10000}) == pytest.approx(5.0)

    def test_steps_fallback_when_no_distance(self):
        assert hs._daily_distance_km({"steps": 10000}) == pytest.approx(8.0)

    def test_zero_when_no_signals(self):
        assert hs._daily_distance_km({}) == pytest.approx(0.0)


class TestSleepHours:
    def test_default_when_missing(self):
        assert hs._sleep_hours({}) == pytest.approx(7.0)

    def test_converts_minutes_and_clamps(self):
        assert hs._sleep_hours({"sleepMinutes": 540}) == pytest.approx(9.0)
        assert hs._sleep_hours({"sleepMinutes": 120}) == pytest.approx(3.0)
        assert hs._sleep_hours({"sleepMinutes": 900}) == pytest.approx(12.0)


class TestRestingHr:
    def test_priority_chain(self):
        assert hs._resting_hr({"restingHeartRate": 48}) == pytest.approx(48.0)
        assert hs._resting_hr({"heartRateMin": 50}) == pytest.approx(50.0)
        assert hs._resting_hr({"heartRateAvg": 60}) == pytest.approx(60.0)
        assert hs._resting_hr({}) == pytest.approx(54.0)

    def test_clamps_extreme_values(self):
        assert hs._resting_hr({"restingHeartRate": 20}) == pytest.approx(38.0)
        assert hs._resting_hr({"restingHeartRate": 120}) == pytest.approx(95.0)


class TestHistoricalDerivedFeatures:
    def test_returns_none_for_empty_history(self):
        assert hs.compute_historical_derived_features([]) is None

    def test_single_day_produces_valid_features(self):
        rows = [{"date_key": "2026-05-01", "distanceMeters": 8000, "sleepMinutes": 420, "hrvRmssd": 60}]
        out = hs.compute_historical_derived_features(rows)
        assert out is not None
        assert 0.35 <= out["acwr_ratio"] <= 2.8
        assert out["acute_load_7d"] >= 0

    def test_seven_day_window_high_confidence_context(self, monkeypatch):
        rows = [
            {
                "date_key": f"2026-05-{i:02d}",
                "distanceMeters": 5000 + i * 200,
                "sleepMinutes": 420,
                "hrvRmssd": 60.0,
            }
            for i in range(1, 8)
        ]
        monkeypatch.setattr(hs, "fetch_user_history", lambda *a, **k: rows)
        ctx = hs.get_history_window_context("u1", "2026-05-07")
        assert ctx["confidence"] == "high"
        assert ctx["days_count"] == 7
        assert ctx["features"] is not None

    @pytest.mark.parametrize(
        ("day_count", "expected_confidence"),
        [(7, "high"), (5, "medium"), (2, "low")],
    )
    def test_confidence_policy_by_day_count(self, monkeypatch, day_count, expected_confidence):
        rows = [
            {"date_key": f"2026-05-{i:02d}", "distanceMeters": 5000, "sleepMinutes": 420}
            for i in range(1, day_count + 1)
        ]
        monkeypatch.setattr(hs, "fetch_user_history", lambda *a, **k: rows)
        ctx = hs.get_history_window_context("u1", "2026-05-09")
        assert ctx["confidence"] == expected_confidence


class TestInjuredYesterdayParsing:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [(True, 1), (False, 0), (1, 1), (0, 0), (None, None)],
    )
    def test_injured_yesterday_from_doc(self, raw, expected):
        doc = {} if raw is None else {"injuredYesterday": raw}
        assert hs._injured_yesterday_from_doc(doc) == expected
