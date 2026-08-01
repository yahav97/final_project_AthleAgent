"""Unit tests for backend Settings defaults and env overrides."""

from __future__ import annotations

from pathlib import Path

import pytest

from config import Settings, settings
from services.ml_policy import load_ml_policy, ml_gate_defaults

pytestmark = pytest.mark.unit


class TestDomainDefaults:
    def test_ml_gates_match_shared_policy_json(self):
        gates = ml_gate_defaults()
        s = Settings()
        assert s.ML_MIN_RECALL_HARD == pytest.approx(gates["min_recall_hard"])
        assert s.ML_MIN_AUC_FOR_LIVE == pytest.approx(gates["min_auc_for_live"])
        assert s.SLEEP_TARGET_HOURS == pytest.approx(
            float(load_ml_policy()["feature_defaults"]["sleep_target_hours"])
        )

    def test_profile_default_age(self):
        assert settings.PROFILE_DEFAULT_AGE == 22
        assert settings.PROFILE_DEFAULT_AGE == int(
            __import__("services.model_features", fromlist=["DEFAULT_FEATURE_VALUES"]).DEFAULT_FEATURE_VALUES["age"]
        )

    def test_confidence_blend_weights_sum_to_one(self):
        s = Settings()
        total = s.CONFIDENCE_HISTORY_WEIGHT + s.CONFIDENCE_QUALITY_WEIGHT
        assert total == pytest.approx(1.0)


class TestEnvOverrides:
    def test_app_env_from_environ(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("APP_ENV", "production")
        s = Settings()
        assert s.APP_ENV == "production"
        assert s.openapi_enabled is False

    def test_log_dir_from_environ(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("LOG_DIR", "/app/logs")
        s = Settings()
        assert s.LOG_DIR == Path("/app/logs")

    def test_risk_cutoffs_from_environ(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("RISK_HIGH_CUTOFF", "0.65")
        monkeypatch.setenv("RISK_MEDIUM_CUTOFF", "0.25")
        s = Settings()
        assert s.RISK_HIGH_CUTOFF == pytest.approx(0.65)
        assert s.RISK_MEDIUM_CUTOFF == pytest.approx(0.25)

    def test_cors_origins_comma_separated(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("CORS_ORIGINS", "http://a.example, http://b.example")
        s = Settings()
        assert s.CORS_ORIGINS == ["http://a.example", "http://b.example"]

    def test_empty_model_path_becomes_none(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("MODEL_PATH", "   ")
        s = Settings()
        assert s.MODEL_PATH is None

    def test_firebase_key_from_environ(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        key = tmp_path / "sa.json"
        key.write_text("{}", encoding="utf-8")
        monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_KEY", str(key))
        s = Settings()
        assert s.FIREBASE_SERVICE_ACCOUNT_KEY == key

    def test_openapi_enabled_only_in_development(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("APP_ENV", "development")
        assert Settings().openapi_enabled is True
        monkeypatch.setenv("APP_ENV", "production")
        assert Settings().openapi_enabled is False
