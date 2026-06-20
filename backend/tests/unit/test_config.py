"""Unit tests for Settings env parsing."""

from __future__ import annotations

import pytest

from config import Settings

pytestmark = pytest.mark.unit


class TestCorsOriginsParsing:
    def test_default_origins(self):
        settings = Settings()
        assert "http://localhost:3000" in settings.CORS_ORIGINS

    def test_comma_separated_env_override(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "http://a.com, http://b.com")
        settings = Settings()
        assert settings.CORS_ORIGINS == ["http://a.com", "http://b.com"]

    def test_json_array_env_override(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", '["http://x.com","http://y.com"]')
        settings = Settings()
        assert settings.CORS_ORIGINS == ["http://x.com", "http://y.com"]
