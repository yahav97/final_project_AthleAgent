"""Unit tests for backend Settings defaults."""

from __future__ import annotations

import pytest

from config import Settings, settings

pytestmark = pytest.mark.unit


class TestDomainDefaults:
    def test_ml_gate_defaults(self):
        s = Settings()
        assert s.ML_MIN_RECALL_HARD == 0.80
        assert s.ML_MIN_AUC_FOR_LIVE == 0.68

    def test_cors_origins(self):
        s = Settings()
        assert "http://localhost:3000" in s.CORS_ORIGINS

    def test_profile_default_age(self):
        assert settings.PROFILE_DEFAULT_AGE == 22
        assert settings.PROFILE_DEFAULT_AGE == int(
            __import__("services.model_features", fromlist=["DEFAULT_FEATURE_VALUES"]).DEFAULT_FEATURE_VALUES["age"]
        )

    def test_risk_band_defaults(self):
        s = Settings()
        assert s.RISK_HIGH_CUTOFF == 0.70
        assert s.RISK_MEDIUM_CUTOFF == 0.20

    def test_history_window_defaults(self):
        s = Settings()
        assert s.HISTORY_LOOKBACK_DAYS == 7
        assert s.HISTORY_CONFIDENCE_HIGH_MIN_DAYS == 7
        assert s.HISTORY_CONFIDENCE_MEDIUM_MIN_DAYS == 4
        assert s.HISTORY_MIN_WATCH_SYNC_SIGNAL_GROUPS == 3

    def test_sleep_feature_defaults(self):
        s = Settings()
        assert s.SLEEP_TARGET_HOURS == 8.0
        assert s.SLEEP_DEBT_SINGLE_DAY_PROXY_SCALE == 1.25

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

    def test_openapi_enabled_in_development(self):
        s = Settings()
        assert s.openapi_enabled is True
