"""Legacy HTTP contract smoke tests — see tests/integration/ for full route coverage."""

import pytest

pytestmark = pytest.mark.integration


def test_predict_daily_production_contract(api_client, mock_daily_prediction_pipeline):
    """Production path returns the three-field JSON contract when inference succeeds."""
    mock_daily_prediction_pipeline()
    response = api_client.post("/predict/daily", json={"userId": "test_uid", "date": "2026-04-19"})

    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == {"risk_level", "risk_score", "prediction_confidence"}
    assert data["risk_level"] in ("Low", "Medium", "High")
    assert 0.0 <= float(data["risk_score"]) <= 1.0
    assert 0.0 <= float(data["prediction_confidence"]) <= 100.0
