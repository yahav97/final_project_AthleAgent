"""Unit tests for profile age imputation."""

from __future__ import annotations

import pytest

from schemas.inference import InjuryPredictionRequest
from services.profile_defaults import resolve_request_age

pytestmark = pytest.mark.unit


class TestResolveRequestAge:
    def test_leaves_payload_when_age_present(self):
        payload = InjuryPredictionRequest(userId="u1", date="2026-04-30", age=31.0)
        resolved = resolve_request_age(payload)
        assert resolved.age == pytest.approx(31.0)
        assert resolved.ageImputed is False

    def test_flags_imputed_when_age_missing(self):
        payload = InjuryPredictionRequest(userId="u1", date="2026-04-30")
        resolved = resolve_request_age(payload)
        assert resolved.age is None
        assert resolved.ageImputed is True
