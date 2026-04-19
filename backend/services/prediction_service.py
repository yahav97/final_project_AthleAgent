"""Orchestration of preprocessing, features, and model.predict_proba."""

from __future__ import annotations

from typing import Any

from ml.model_loader import get_model
from schemas.inference import InjuryPredictionRequest
from services.preprocessing import injury_request_to_model_dataframe


def _recommendation(probability: float, acwr: float) -> str:
    if probability >= 0.6:
        return "Reduce training load today; prioritize sleep and recovery."
    if probability >= 0.35 or acwr >= 1.35:
        return "Moderate risk: consider lighter session and monitor soreness and sleep."
    if acwr >= 1.2:
        return "ACWR elevated: keep volume stable and avoid sharp spikes this week."
    return "Maintain current load; continue monitoring sleep and subjective readiness."


def predict_injury_risk(payload: InjuryPredictionRequest) -> dict[str, Any]:
    """
    Run preprocessing → feature row → sklearn ``predict_proba`` (injury positive class).

    If ``injury_model.pkl`` is not present on the server, returns a conservative demo
    response so local development and CI still behave predictably.
    """
    df = injury_request_to_model_dataframe(payload)
    acwr = float(df["acwr_ratio"].iloc[0])

    model = get_model()
    if model is None:
        return {
            "risk_level": "Low",
            "risk_score": 0.12,
            "recommendation": "Model artifact not loaded; demo response only. Train/copy injury_model.pkl to backend/.",
        }

    proba = float(model.predict_proba(df)[0, 1])
    risk_level = "High" if proba > 0.6 else "Medium" if proba > 0.3 else "Low"

    return {
        "risk_level": risk_level,
        "risk_score": round(proba, 4),
        "recommendation": _recommendation(proba, acwr),
    }
