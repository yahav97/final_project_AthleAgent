from services.history_service import compute_historical_derived_features, get_history_window_context


def test_compute_historical_derived_features_returns_rolling_values():
    rows = []
    for i in range(1, 8):
        rows.append(
            {
                "date_key": f"2026-04-0{i}",
                "distanceMeters": 1000 * i,  # 1..7 km
                "sleepMinutes": 420 + i * 5,
                "heartRateMin": 50 + i % 3,
                "heartRateAvg": 58 + i % 2,
            }
        )

    out = compute_historical_derived_features(rows)
    assert out is not None
    assert 0.35 <= out["acwr_ratio"] <= 2.8
    assert out["acute_load_7d"] > 0
    assert out["chronic_load_21d"] > 0
    assert -15.0 <= out["hrv_drop"] <= 15.0


def test_history_window_context_confidence_low_for_short_history(monkeypatch):
    from services import history_service as hs

    monkeypatch.setattr(
        hs,
        "fetch_user_history",
        lambda user_id, date_key, lookback_days=7, include_target_day=True: [
            {"date_key": "2026-04-19", "distanceMeters": 4500, "sleepMinutes": 420}
        ],
    )
    ctx = get_history_window_context("u1", "2026-04-19")
    assert ctx["confidence"] == "low"
    assert int(ctx["days_count"]) == 1


def test_history_window_context_can_exclude_target_day(monkeypatch):
    from services import history_service as hs

    captured: dict[str, object] = {}

    def _fake_fetch(user_id, date_key, lookback_days=7, include_target_day=True):
        captured["include_target_day"] = include_target_day
        return []

    monkeypatch.setattr(hs, "fetch_user_history", _fake_fetch)
    _ = hs.get_history_window_context("u1", "2026-04-19", include_target_day=False)
    assert captured["include_target_day"] is False


def test_compute_historical_features_with_missing_days_uses_available_average():
    rows = [
        {"date_key": "2026-04-20", "distanceMeters": 4000, "sleepMinutes": 420, "heartRateAvg": 58},
        {"date_key": "2026-04-22", "distanceMeters": 6000, "sleepMinutes": 430, "heartRateAvg": 59},
        {"date_key": "2026-04-24", "distanceMeters": 5000, "sleepMinutes": 410, "heartRateAvg": 60},
        {"date_key": "2026-04-25", "distanceMeters": 7000, "sleepMinutes": 440, "heartRateAvg": 57},
        {"date_key": "2026-04-27", "distanceMeters": 8000, "sleepMinutes": 435, "heartRateAvg": 56},
    ]
    out = compute_historical_derived_features(rows)
    assert out is not None
    # 5 days available out of weekly window -> use available mean load (6.0 km)
    assert abs(out["acute_load_7d"] - 6.0) < 1e-6
    assert 0.35 <= out["acwr_ratio"] <= 2.8
