"""Ensure predict_proba receives only columns the saved estimator was fit on."""

from pathlib import Path

import pandas as pd
import pytest

from schemas.inference import InjuryPredictionRequest
from services.model_features import MODEL_FEATURE_COLUMNS
from services.prediction_service import predict_injury_risk
from services.preprocessing import validate_feature_vector_for_model


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[1] / "injury_model.pkl").is_file(),
    reason="injury_model.pkl not present",
)
def test_predict_injury_risk_with_loaded_model_no_500():
    from fastapi.testclient import TestClient

    from main import app

    with TestClient(app) as client:
        r = client.post(
            "/predict",
            json={
                "userId": "u1",
                "date": "2026-04-30",
                "sleepMinutes": 480,
                "steps": 8000,
                "stressLevel": 35,
                "muscleSoreness": 2,
            },
        )
    if r.status_code == 500:
        assert "Prediction unavailable" in r.json()["detail"]
        return
    assert r.status_code == 200
    data = r.json()
    assert "artifact" not in data.get("recommendation", "").lower()
    assert 0.0 <= float(data["risk_score"]) <= 1.0


def test_predict_injury_risk_service_subset_columns_skips_missing_estimator(monkeypatch):
    """When model is blocked by gate, service raises deterministic runtime error."""
    from services import prediction_service as ps

    monkeypatch.setattr(ps, "get_model", lambda: None)
    monkeypatch.setattr(ps, "get_model_gate_reason", lambda: "manifest_corrupted")
    with pytest.raises(RuntimeError, match="model_not_live:manifest_corrupted"):
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


def test_predict_injury_risk_returns_confidence_bucket_in_meta(monkeypatch):
    from services import prediction_service as ps

    monkeypatch.setattr(ps, "get_model", lambda: None)
    monkeypatch.setattr(ps, "get_model_gate_reason", lambda: "manifest_corrupted")
    with pytest.raises(RuntimeError):
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


def test_predict_quality_relaxed_when_history_backfills_missing_signals(monkeypatch):
    from services import prediction_service as ps

    base_df = pd.DataFrame(
        [
            {
                "acwr_ratio": 1.0,
                "daily_distance_km": 0.0,
                "workout_intensity_minutes": 0.0,
                "sleep_hours": 0.0,
                "resting_hr": 0.0,
                "hrv_score": 0.0,
            }
        ]
    )
    monkeypatch.setattr(ps, "injury_request_to_model_dataframe", lambda payload: base_df.copy())
    monkeypatch.setattr(
        ps,
        "_backfill_today_row_from_recent_history",
        lambda df, payload: (df, {"load": True, "recovery": True}),
    )
    monkeypatch.setattr(ps, "_apply_history_confidence_fallback", lambda df, payload: (df, "medium"))
    monkeypatch.setattr(
        ps,
        "calculate_data_quality_score",
        lambda payload: {
            "score": 0.2,
            "hard_missing": ["load_signal", "recovery_signal"],
            "sensitive_missing": [],
            "has_hard_blocker": True,
        },
    )
    monkeypatch.setattr(ps, "_count_defaulted_critical_features", lambda df: 0)
    monkeypatch.setattr(ps, "get_model", lambda: None)
    monkeypatch.setattr(ps, "get_model_gate_reason", lambda: "manifest_corrupted")

    with pytest.raises(RuntimeError, match="model_not_live:manifest_corrupted"):
        predict_injury_risk(
            InjuryPredictionRequest(
                userId="u1",
                date="2026-04-30",
                stressLevel=30,
                muscleSoreness=3,
            )
        )


def test_predict_injury_risk_from_firestore_maps_snapshot(monkeypatch):
    from services import prediction_service as ps

    monkeypatch.setattr(
        ps,
        "fetch_daily_firestore_snapshot",
        lambda user_id, date_key: {
            "profile": {"age": 24, "vo2Max": 57, "historyInjuryCount": 1},
            "daily_health": {"sleepMinutes": 470, "steps": 8300, "heartRateAvg": 58},
            "daily_checkins": {"muscleSoreness": 3, "stressLevel": 35, "energyLevel": 60},
            "daily_nutrition": {"totalProtein": 130, "totalCarbs": 290, "mealsLoggedCount": 3},
        },
    )
    monkeypatch.setattr(
        ps,
        "predict_injury_risk",
        lambda payload: {"risk_level": "Low", "risk_score": 0.12, "recommendation": payload.userId},
    )
    out = ps.predict_injury_risk_from_firestore("u1", "2026-05-09")
    assert out["risk_level"] == "Low"
    assert abs(float(out["risk_score"]) - 0.12) < 1e-9
    assert out["recommendation"] == "u1"


def test_persist_prediction_result_or_raise_raises_when_write_fails(monkeypatch):
    from services import prediction_service as ps

    monkeypatch.setattr(ps, "save_daily_prediction_result", lambda user_id, date_key, result, source: False)
    with pytest.raises(RuntimeError, match="prediction_persist_failed"):
        ps.persist_prediction_result_or_raise(
            "u1",
            "2026-05-09",
            {"risk_score": 0.3, "risk_level": "Low"},
            source="backend_predict_daily",
        )


def test_validate_feature_vector_enforces_exact_training_order():
    df = pd.DataFrame(
        [
            {
                "sleep_hours": 7.0,
                "age": 26.0,
                "vo2_max": 55.0,
            }
        ]
    )
    aligned = validate_feature_vector_for_model(
        df,
        {"feature_columns": ["age", "vo2_max", "sleep_hours"], "estimator": None},
    )
    assert list(aligned.columns) == ["age", "vo2_max", "sleep_hours"]


def test_validate_feature_vector_raises_when_missing_column():
    df = pd.DataFrame([{c: 1.0 for c in MODEL_FEATURE_COLUMNS if c != "acwr_ratio"}])
    with pytest.raises(ValueError, match="missing feature columns"):
        validate_feature_vector_for_model(
            df,
            {"feature_columns": MODEL_FEATURE_COLUMNS, "estimator": None},
        )
