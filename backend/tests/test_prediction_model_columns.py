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
            json={"sleepMinutes": 480, "steps": 8000, "stressLevel": 35, "muscleSoreness": 2},
        )
    assert r.status_code == 200
    data = r.json()
    assert "artifact" not in data.get("recommendation", "").lower()
    assert 0.0 <= float(data["risk_score"]) <= 1.0


def test_predict_injury_risk_service_subset_columns_skips_missing_estimator(monkeypatch):
    """When hard requirements are missing, service returns conservative fallback."""
    from services import prediction_service as ps

    monkeypatch.setattr(ps, "get_model", lambda: None)
    out = predict_injury_risk(InjuryPredictionRequest(sleepMinutes=480))
    assert out["risk_score"] == 0.08
    assert "insufficient data" in out["recommendation"].lower()
    assert 0.0 <= float(out["data_quality_score"]) <= 1.0
    assert out["data_quality_status"] in ("Excellent", "Good", "Fair", "Poor")


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
