"""Firestore snapshot → InjuryPredictionRequest parity helpers."""

from services.history_service import stable_athlete_numeric_id
from services.model_features import MODEL_FEATURE_COLUMNS, TRAINING_CSV_EXCLUDE_COLUMNS
from services.prediction_service import (
    injury_prediction_request_from_firestore_snapshot,
    training_base_feature_dict_from_request,
)


def test_training_base_column_contract():
    excluded = set(TRAINING_CSV_EXCLUDE_COLUMNS)
    base = [c for c in MODEL_FEATURE_COLUMNS if c not in excluded]
    assert len(base) == 20


def test_stable_athlete_numeric_id_is_deterministic():
    assert stable_athlete_numeric_id("abc") == stable_athlete_numeric_id("abc")
    assert stable_athlete_numeric_id("abc") != stable_athlete_numeric_id("abd")


def test_injury_prediction_request_prefers_heart_rate_avg_alias():
    snap = {
        "profile": {},
        "daily_health": {"sleepMinutes": 420},
        "daily_health_yesterday": {"avgHeartRate": 71, "steps": 6000},
        "daily_checkins": {"stressLevel": 40, "muscleSoreness": 3},
        "daily_nutrition": {},
    }
    req = injury_prediction_request_from_firestore_snapshot("u1", "2026-05-01", snap)
    assert req.heartRateAvg == 71


def test_injury_prediction_request_heart_rate_avg_wins_over_avg():
    snap = {
        "profile": {},
        "daily_health": {"sleepMinutes": 420},
        "daily_health_yesterday": {"heartRateAvg": 60, "avgHeartRate": 99, "steps": 100},
        "daily_checkins": {},
        "daily_nutrition": {},
    }
    req = injury_prediction_request_from_firestore_snapshot("u1", "2026-05-02", snap)
    assert req.heartRateAvg == 60


def test_training_base_feature_dict_shape(monkeypatch):
    monkeypatch.setattr(
        "services.history_service.get_history_window_context",
        lambda *a, **k: {
            "days_count": 1,
            "confidence": "low",
            "features": None,
            "recent_row": None,
        },
    )
    snap = {
        "profile": {},
        "daily_health": {"sleepMinutes": 480},
        "daily_health_yesterday": {"steps": 7000, "distanceMeters": 4000},
        "daily_checkins": {"stressLevel": 35, "muscleSoreness": 2},
        "daily_nutrition": {"totalProtein": 100, "totalCarbs": 200, "mealsLoggedCount": 2},
    }
    payload = injury_prediction_request_from_firestore_snapshot("u2", "2026-05-03", snap)
    row = training_base_feature_dict_from_request(payload)
    assert len(row) == 20
    assert "acwr_ratio_ma7" not in row
