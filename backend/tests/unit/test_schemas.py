"""Unit tests for shared Pydantic schema validators."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.inference import (
    DailyPredictionTriggerRequest,
    InjuryPredictionRequest,
    InjuryPredictionResponse,
)

pytestmark = pytest.mark.unit


class TestDateKeyValidation:
    def test_accepts_valid_date_on_trigger(self):
        req = DailyPredictionTriggerRequest(userId="u1", date="2026-04-30")
        assert req.date == "2026-04-30"

    def test_rejects_invalid_calendar_date(self):
        with pytest.raises(ValidationError):
            DailyPredictionTriggerRequest(userId="u1", date="2026-13-40")

    def test_optional_date_allows_none(self):
        req = InjuryPredictionRequest(userId="u1")
        assert req.date is None


class TestRiskLevelValidation:
    def test_accepts_production_levels(self):
        for level in ("Low", "Medium", "High"):
            out = InjuryPredictionResponse(
                risk_level=level,
                risk_score=0.4,
                prediction_confidence=70.0,
            )
            assert out.risk_level == level

    def test_rejects_unknown_level(self):
        with pytest.raises(ValidationError):
            InjuryPredictionResponse(
                risk_level="Critical",
                risk_score=0.9,
                prediction_confidence=80.0,
            )
