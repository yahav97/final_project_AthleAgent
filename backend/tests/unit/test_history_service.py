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


class TestSleepHours:
    def test_default_when_missing(self):
        assert hs._sleep_hours({}) == pytest.approx(7.0)

    def test_converts_minutes_and_clamps(self):
        assert hs._sleep_hours({"sleepMinutes": 540}) == pytest.approx(9.0)
        assert hs._sleep_hours({"sleepMinutes": 120}) == pytest.approx(3.0)
        assert hs._sleep_hours({"sleepMinutes": 900}) == pytest.approx(12.0)


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


class TestFetchUserHistory:
    def test_reads_documents_by_date_key_not_collection_stream(self, monkeypatch):
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
                if self.collection == "daily_health" and self.key == "2026-05-03":
                    return _Snapshot(True, {"steps": 5000, "sleepMinutes": 420})
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

        monkeypatch.setattr(hs, "_get_firestore_client", lambda: _Db())
        rows = hs.fetch_user_history("u1", "2026-05-03", lookback_days=7, include_target_day=True)

        assert len(rows) == 1
        assert rows[0]["date_key"] == "2026-05-03"
        assert rows[0]["steps"] == 5000
        assert get_calls
        assert all(call[0] in ("daily_health", "daily_checkins") for call in get_calls)
        assert ("daily_health", "2026-05-03") in get_calls
