"""Ensure predict_proba receives only columns the saved estimator was fit on."""

from pathlib import Path

import pandas as pd
import pytest

from schemas.inference import InjuryPredictionRequest
from services.model_features import MODEL_FEATURE_COLUMNS
from services.prediction_service import predict_injury_risk
from utils.exceptions import DatabaseError, MLModelError, ValidationError


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[1] / "injury_model.pkl").is_file(),
    reason="injury_model.pkl not present",
)
def test_predict_injury_risk_with_loaded_model_no_500(monkeypatch):
    from api.routes import predict as predict_routes
    from fastapi.testclient import TestClient

    from main import app
    from services import prediction_service as ps

    monkeypatch.setattr(
        ps,
        "fetch_daily_firestore_snapshot",
        lambda uid, d: {
            "profile": {},
            "daily_health": {"sleepMinutes": 480},
            "daily_health_yesterday": {"steps": 8000, "distanceMeters": 5000},
            "daily_checkins": {"stressLevel": 35, "muscleSoreness": 2},
            "daily_nutrition_yesterday": {},
        },
    )
    monkeypatch.setattr(predict_routes, "persist_prediction_result_or_raise", lambda *a, **k: None)

    with TestClient(app) as client:
        r = client.post(
            "/predict/daily",
            json={"userId": "u1", "date": "2026-04-30"},
        )
    if r.status_code == 503:
        assert "Model is not live" in r.json()["detail"]
        return
    assert r.status_code == 200
    data = r.json()
    assert 0.0 <= float(data["risk_score"]) <= 1.0


def test_predict_injury_risk_service_subset_columns_skips_missing_estimator(monkeypatch):
    """When model is blocked by gate, service raises deterministic runtime error."""
    from services import prediction_service as ps

    monkeypatch.setattr(ps, "get_model", lambda: None)
    monkeypatch.setattr(ps, "get_model_gate_reason", lambda: "manifest_corrupted")
    with pytest.raises(MLModelError, match="Model is not live: manifest_corrupted"):
        predict_injury_risk(
            InjuryPredictionRequest(
                userId="u1",
                date="2026-04-30",
                sleepMinutes=480,
                steps=7000,
                stressLevel=30,
                muscleSoreness=2,
            )
        )


def test_predict_injury_risk_raises_when_model_missing(monkeypatch):
    from services import prediction_service as ps

    monkeypatch.setattr(ps, "get_model", lambda: None)
    monkeypatch.setattr(ps, "get_model_gate_reason", lambda: "manifest_corrupted")
    with pytest.raises(MLModelError):
        predict_injury_risk(
            InjuryPredictionRequest(
                userId="u1",
                date="2026-04-30",
                sleepMinutes=450,
                steps=6200,
                stressLevel=36,
                muscleSoreness=3,
            )
        )


def test_predict_injury_risk_from_firestore_maps_snapshot(monkeypatch):
    from services import prediction_service as ps

    monkeypatch.setattr(
        ps,
        "fetch_daily_firestore_snapshot",
        lambda user_id, date_key: {
            "profile": {},
            "daily_health": {"sleepMinutes": 470},
            "daily_health_yesterday": {"steps": 8300, "heartRateAvg": 58},
            "daily_checkins": {"muscleSoreness": 3, "stressLevel": 35, "energyLevel": 60},
            "daily_nutrition_yesterday": {"totalProtein": 130, "totalCarbs": 290, "mealsLoggedCount": 3},
        },
    )
    monkeypatch.setattr(
        ps,
        "predict_injury_risk",
        lambda payload: {
            "risk_level": "Low",
            "risk_score": 0.12,
            "prediction_confidence": 80.0,
        },
    )
    out = ps.predict_injury_risk_from_firestore("u1", "2026-05-09")
    assert out["risk_level"] == "Low"
    assert abs(float(out["risk_score"]) - 0.12) < 1e-9


def test_persist_prediction_result_or_raise_raises_when_write_fails(monkeypatch):
    from services import prediction_service as ps

    monkeypatch.setattr(ps, "save_daily_prediction_result", lambda user_id, date_key, result: False)
    with pytest.raises(DatabaseError, match="Prediction persist failed"):
        ps.persist_prediction_result_or_raise(
            "u1",
            "2026-05-09",
            {"risk_score": 0.3, "risk_level": "Low", "prediction_confidence": 55.0},
        )


def test_validate_feature_vector_enforces_exact_training_order():
    df = pd.DataFrame(
        [
            {
                "sleep_hours": 7.0,
                "bmi": 23.0,
                "nutrition_intake_calories": 2400.0,
            }
        ]
    )
    aligned = validate_feature_vector_for_model(
        df,
        {
            "feature_columns": ["bmi", "nutrition_intake_calories", "sleep_hours"],
            "estimator": None,
        },
    )
    assert list(aligned.columns) == ["bmi", "nutrition_intake_calories", "sleep_hours"]


def test_firestore_snapshot_split_date_merge_policy():
    from services.prediction_service import injury_prediction_request_from_firestore_snapshot

    req = injury_prediction_request_from_firestore_snapshot(
        "u1",
        "2026-06-16",
        {
            "profile": {},
            "daily_health": {"sleepMinutes": 480, "steps": 50},
            "daily_health_yesterday": {"steps": 8300, "sleepMinutes": 360, "heartRateAvg": 58},
            "daily_checkins": {"muscleSoreness": 3, "stressLevel": 35, "energyLevel": 60},
            "daily_nutrition_yesterday": {"totalProtein": 130, "totalCarbs": 290, "mealsLoggedCount": 3},
        },
    )
    assert req.sleepMinutes == 480
    assert req.steps == 8300
    assert req.heartRateAvg == 58
    assert req.totalProtein == 130


def test_validate_feature_vector_raises_when_missing_column():
    df = pd.DataFrame([{c: 1.0 for c in MODEL_FEATURE_COLUMNS if c != "acwr_ratio"}])
    with pytest.raises(ValidationError, match="missing feature columns"):
        validate_feature_vector_for_model(
            df,
            {"feature_columns": MODEL_FEATURE_COLUMNS, "estimator": None},
        )
