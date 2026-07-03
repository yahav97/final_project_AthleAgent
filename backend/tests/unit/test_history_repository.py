"""Unit tests for history repository and rolling features."""

from __future__ import annotations

import pytest
import pandas as pd

from services.feature_engineering import compute_derived_features
from services.history.day_quality import (
    WATCH_SYNC_SIGNAL_GROUPS,
    count_watch_sync_signal_groups,
    is_quality_history_day,
)
from services.history.history_merge import merge_wake_up_day_row
from services.history.repository import (
    fetch_user_history,
    get_history_window_context,
    history_confidence_from_quality_days,
    stable_athlete_numeric_id,
)
from services.history.rolling_features import (
    compute_historical_derived_features,
    sleep_hours,
    sleep_hours_from_doc,
)
from services.preprocessing.request_features import add_same_day_composite_features

pytestmark = pytest.mark.unit


class TestHistoryConfidenceBoundaries:
    @pytest.mark.parametrize(
        ("quality_days", "expected"),
        [
            (0, "low"),
            (3, "low"),
            (4, "medium"),
            (6, "medium"),
            (7, "high"),
        ],
    )
    def test_history_confidence_from_quality_days(self, quality_days, expected):
        from schemas.enums import HistoryConfidence

        level = history_confidence_from_quality_days(quality_days)
        assert level == HistoryConfidence(expected)


class TestStableAthleteId:
    def test_deterministic_for_same_uid(self):
        assert stable_athlete_numeric_id("firebase-uid-abc") == stable_athlete_numeric_id(
            "firebase-uid-abc"
        )

    def test_different_uids_produce_different_ids(self):
        a = stable_athlete_numeric_id("athlete-a")
        b = stable_athlete_numeric_id("athlete-b")
        assert a != b

    def test_always_positive(self):
        assert stable_athlete_numeric_id("") > 0


class TestSleepHours:
    def test_default_when_missing(self):
        assert sleep_hours({}) == pytest.approx(7.0)

    def test_converts_minutes_and_clamps(self):
        assert sleep_hours({"sleepMinutes": 540}) == pytest.approx(9.0)
        assert sleep_hours({"sleepMinutes": 120}) == pytest.approx(3.0)
        assert sleep_hours({"sleepMinutes": 900}) == pytest.approx(12.0)


class TestHistoryDayQuality:
    def test_watch_sync_signal_groups_are_four_named_categories(self):
        assert set(WATCH_SYNC_SIGNAL_GROUPS) == {"load", "sleep", "heart", "energy"}

    def _synced_physical_day(self, **extra: object) -> dict:
        return {
            "distanceMeters": 5000,
            "steps": 7200,
            "heartRateAvg": 58,
            "activeCalories": 420,
            **extra,
        }

    def test_requires_watch_sync_signal_bundle(self):
        assert is_quality_history_day(self._synced_physical_day()) is True
        assert is_quality_history_day(
            {"distanceMeters": 5000, "sleepMinutes": 420, "heartRateAvg": 58}
        ) is True
        assert is_quality_history_day({"distanceMeters": 5000, "sleepMinutes": 420}) is False
        assert is_quality_history_day({"distanceMeters": 5000}) is False
        assert is_quality_history_day({"sleepMinutes": 420}) is False

    def test_counts_signal_groups(self):
        row = self._synced_physical_day(sleepMinutes=420)
        assert count_watch_sync_signal_groups(row) == 4

    def test_sparse_history_downgrades_confidence(self, monkeypatch):
        rows = [
            self._synced_physical_day(date_key=f"2026-05-{i:02d}")
            if i <= 2
            else {"date_key": f"2026-05-{i:02d}", "distanceMeters": 0, "sleepMinutes": 0}
            for i in range(1, 8)
        ]
        monkeypatch.setattr(
            "services.history.repository.fetch_user_history",
            lambda *args, **kwargs: rows,
        )
        ctx = get_history_window_context("u1", "2026-05-07")
        assert ctx["days_count"] == 7
        assert ctx["quality_days_count"] == 2
        assert ctx["confidence"] == "low"


    def test_split_sync_documents_merge_into_quality_day(self):
        row = merge_wake_up_day_row(
            "2026-05-07",
            {"steps": 9000, "heartRateAvg": 55, "activeCalories": 500},
            {"sleepMinutes": 430},
            {"stressLevel": 40},
        )
        assert row is not None
        assert is_quality_history_day(row)
        assert row["steps"] == 9000
        assert row["sleepMinutes"] == 430
        assert row["stressLevel"] == 40


class TestHistoricalDerivedFeatures:
    def test_returns_none_for_empty_history(self):
        assert compute_historical_derived_features([]) is None

    def test_single_day_produces_valid_features(self):
        rows = [{"date_key": "2026-05-01", "distanceMeters": 8000, "sleepMinutes": 420, "hrvRmssd": 60}]
        out = compute_historical_derived_features(rows)
        assert out is not None
        assert 0.35 <= out["acwr_ratio"] <= 2.8
        assert out["acute_load_7d"] >= 0
        assert out["acwr_ratio_ma7"] == pytest.approx(out["acwr_ratio"])
        assert out["sleep_hours_ma7"] == pytest.approx(sleep_hours(rows[0]))

    def test_seven_day_window_high_confidence_context(self, monkeypatch):
        rows = [
            {
                "date_key": f"2026-05-{i:02d}",
                "distanceMeters": 5000 + i * 200,
                "sleepMinutes": 420,
                "heartRateAvg": 58,
                "activeCalories": 400 + i * 10,
                "hrvRmssd": 60.0,
            }
            for i in range(1, 8)
        ]

        monkeypatch.setattr(
            "services.history.repository.fetch_user_history",
            lambda *args, **kwargs: rows,
        )
        ctx = get_history_window_context("u1", "2026-05-07")
        assert ctx["confidence"] == "high"
        assert ctx["days_count"] == 7
        assert ctx["features"] is not None
        assert "acwr_ratio_ma7" in ctx["features"]
        assert "sleep_hours_ma7" in ctx["features"]

    @pytest.mark.parametrize(
        ("day_count", "expected_confidence"),
        [(7, "high"), (5, "medium"), (2, "low")],
    )
    def test_confidence_policy_by_day_count(self, monkeypatch, day_count, expected_confidence):
        rows = [
            {
                "date_key": f"2026-05-{i:02d}",
                "distanceMeters": 5000,
                "sleepMinutes": 420,
                "heartRateAvg": 58,
                "activeCalories": 420,
            }
            for i in range(1, day_count + 1)
        ]

        monkeypatch.setattr(
            "services.history.repository.fetch_user_history",
            lambda *args, **kwargs: rows,
        )
        ctx = get_history_window_context("u1", "2026-05-09")
        assert ctx["confidence"] == expected_confidence


class TestFetchUserHistory:
    def test_merges_physical_yesterday_with_sleep_and_checkin_today(self, monkeypatch):
        get_calls: list[tuple[str, str]] = []

        class _Snapshot:
            def __init__(self, exists: bool, data: dict | None = None) -> None:
                self.exists = exists
                self._data = data or {}

            def to_dict(self) -> dict:
                return self._data

        class _DocRef:
            def __init__(self, collection: str, key: str) -> None:
                self.collection = collection
                self.key = key

            def get(self) -> _Snapshot:
                get_calls.append((self.collection, self.key))
                if self.collection == "daily_health" and self.key == "2026-05-02":
                    return _Snapshot(
                        True,
                        {"steps": 5000, "heartRateAvg": 58, "activeCalories": 400},
                    )
                if self.collection == "daily_health" and self.key == "2026-05-03":
                    return _Snapshot(True, {"sleepMinutes": 420})
                if self.collection == "daily_checkins" and self.key == "2026-05-03":
                    return _Snapshot(True, {"stressLevel": 35})
                return _Snapshot(False)

        class _Collection:
            def __init__(self, name: str) -> None:
                self.name = name

            def document(self, key: str) -> _DocRef:
                return _DocRef(self.name, key)

        class _UserDoc:
            def collection(self, name: str) -> _Collection:
                return _Collection(name)

        class _Db:
            def collection(self, name: str):
                class _Users:
                    def document(self, uid: str) -> _UserDoc:
                        return _UserDoc()

                return _Users()

        monkeypatch.setattr("services.history.repository.get_firestore_client", lambda: _Db())
        rows = fetch_user_history("u1", "2026-05-03", lookback_days=1, include_target_day=True)

        assert len(rows) == 1
        assert rows[0]["date_key"] == "2026-05-03"
        assert rows[0]["steps"] == 5000
        assert rows[0]["sleepMinutes"] == 420
        assert rows[0]["stressLevel"] == 35
        assert ("daily_health", "2026-05-02") in get_calls
        assert ("daily_health", "2026-05-03") in get_calls
        assert ("daily_checkins", "2026-05-03") in get_calls

    def test_prediction_window_uses_wake_days_through_yesterday(self, monkeypatch):
        requested_health_keys: list[str] = []

        class _Snapshot:
            def __init__(self, exists: bool, data: dict | None = None) -> None:
                self.exists = exists
                self._data = data or {}

            def to_dict(self) -> dict:
                return self._data

        class _DocRef:
            def __init__(self, collection: str, key: str) -> None:
                self.collection = collection
                self.key = key

            def get(self) -> _Snapshot:
                if self.collection == "daily_health":
                    requested_health_keys.append(self.key)
                return _Snapshot(False)

        class _Collection:
            def __init__(self, name: str) -> None:
                self.name = name

            def document(self, key: str) -> _DocRef:
                return _DocRef(self.name, key)

        class _UserDoc:
            def collection(self, name: str) -> _Collection:
                return _Collection(name)

        class _Db:
            def collection(self, name: str):
                class _Users:
                    def document(self, uid: str) -> _UserDoc:
                        return _UserDoc()

                return _Users()

        monkeypatch.setattr("services.history.repository.get_firestore_client", lambda: _Db())
        fetch_user_history("u1", "2026-05-07", lookback_days=7, include_target_day=False)

        # Wake-up days D-7..D-1 plus physical docs one day earlier.
        assert requested_health_keys
        assert "2026-05-06" in requested_health_keys
        assert "2026-05-07" not in requested_health_keys
        assert "2026-04-30" in requested_health_keys


def _training_style_ma7(acwr_values: list[float], sleep_values: list[float]) -> tuple[float, float]:
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
