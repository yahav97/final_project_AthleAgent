"""Unit tests for Settings env parsing."""

from __future__ import annotations

import pytest

from config import Settings, settings

pytestmark = pytest.mark.unit


class TestCorsOriginsParsing:
    def test_default_origins(self):
        s = Settings()
        assert "http://localhost:3000" in s.CORS_ORIGINS

    def test_comma_separated_env_override(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "http://a.com, http://b.com")
        s = Settings()
        assert s.CORS_ORIGINS == ["http://a.com", "http://b.com"]

    def test_json_array_env_override(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", '["http://x.com","http://y.com"]')
        s = Settings()
        assert s.CORS_ORIGINS == ["http://x.com", "http://y.com"]


class TestDomainDefaults:
    def test_ml_gate_defaults(self):
        s = Settings()
        assert s.ML_MIN_RECALL_HARD == 0.80
        assert s.ML_MIN_AUC_FOR_LIVE == 0.68
        assert s.ML_DEGRADED_AUC_OFFSET == 0.02

    def test_risk_band_defaults(self):
        s = Settings()
        assert s.RISK_HIGH_CUTOFF == 0.70
        assert s.RISK_MEDIUM_CUTOFF == 0.20

    def test_history_window_defaults(self):
        s = Settings()
        assert s.HISTORY_LOOKBACK_DAYS == 7
        assert s.HISTORY_CONFIDENCE_HIGH_MIN_DAYS == 7
        assert s.HISTORY_CONFIDENCE_MEDIUM_MIN_DAYS == 4

    def test_feature_flags_default_off(self):
        s = Settings()
        assert s.ENABLE_TEST_PREDICT_ENDPOINT is False

    def test_confidence_blend_weights_sum_to_one(self):
        s = Settings()
        total = s.CONFIDENCE_HISTORY_WEIGHT + s.CONFIDENCE_QUALITY_WEIGHT
        assert total == pytest.approx(1.0)

    def test_singleton_settings_matches_fresh_instance_defaults(self):
        fresh = Settings()
        assert fresh.ML_MIN_RECALL_HARD == settings.ML_MIN_RECALL_HARD
        assert fresh.RISK_HIGH_CUTOFF == settings.RISK_HIGH_CUTOFF

