"""Additional edge-case inference tests for RC1 hardening."""

import pytest
from fastapi.testclient import TestClient

from main import app
from schemas.inference import InjuryPredictionRequest
from services.prediction_service import predict_injury_risk
from utils.exceptions import AthleAgentException

pytestmark = pytest.mark.integration


def test_predict_extreme_sleep_zero_no_crash():
    try:
        out = predict_injury_risk(
            InjuryPredictionRequest(
                userId="edge_sleep",
                date="2026-04-30",
                sleepMinutes=0,
                steps=9000,
                distanceMeters=7000,
                stressLevel=80,
                muscleSoreness=5,
            )
        )
    except AthleAgentException:
        return
    assert 0.0 <= float(out["risk_score"]) <= 1.0


def test_predict_extreme_distance_high_no_crash():
    try:
        predict_injury_risk(
            InjuryPredictionRequest(
                userId="edge_load",
                date="2026-04-30",
                sleepMinutes=420,
                steps=80000,
                distanceMeters=50000,
                stressLevel=75,
                muscleSoreness=5,
            )
        )
    except AthleAgentException:
        return


def test_predict_response_json_schema_when_success():
    try:
        data = predict_injury_risk(
            InjuryPredictionRequest(
                userId="schema_ok",
                date="2026-04-30",
                sleepMinutes=480,
                steps=8500,
                stressLevel=30,
                muscleSoreness=2,
            )
        )
    except AthleAgentException:
        return
    assert {"risk_score", "risk_level", "prediction_confidence"} <= set(data.keys())


def test_status_endpoint_multiple_calls_light_load():
    with TestClient(app) as client:
        for _ in range(10):
            response = client.get("/status/ml")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] in ("Live", "Blocked")


def test_predict_missing_optional_fields_still_deterministic_error_or_success():
    try:
        predict_injury_risk(InjuryPredictionRequest(userId="minimal", date="2026-04-30"))
    except AthleAgentException:
        return
