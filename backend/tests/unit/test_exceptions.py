"""Unit tests for domain exception types and HTTP mapping."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from utils.exceptions import (
    AthleAgentException,
    DatabaseError,
    MLModelError,
    ValidationError,
    register_exception_handlers,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def exception_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/ml-blocked")
    def ml_blocked() -> None:
        raise MLModelError("Model is not live: manifest_corrupted", code="model_not_live:manifest_corrupted")

    @app.get("/persist-failed")
    def persist_failed() -> None:
        raise DatabaseError("Prediction persist failed", code="prediction_persist_failed")

    @app.get("/invalid-features")
    def invalid_features() -> None:
        raise ValidationError("Feature vector contains NaN values")

    return app


class TestExceptionTypes:
    def test_base_exception_stores_code(self):
        exc = AthleAgentException("something failed", code="something_failed")
        assert str(exc) == "something failed"
        assert exc.code == "something_failed"
        assert exc.status_code == 500

    def test_subclasses_set_status_codes(self):
        assert MLModelError("x").status_code == 503
        assert DatabaseError("x").status_code == 503
        assert ValidationError("x").status_code == 422


class TestExceptionHandlers:
    def test_ml_model_error_maps_to_503(self, exception_app):
        with TestClient(exception_app) as client:
            response = client.get("/ml-blocked")
        assert response.status_code == 503
        data = response.json()
        assert "Model is not live" in data["detail"]
        assert data["code"] == "model_not_live:manifest_corrupted"

    def test_database_error_maps_to_503(self, exception_app):
        with TestClient(exception_app) as client:
            response = client.get("/persist-failed")
        assert response.status_code == 503
        assert response.json()["code"] == "prediction_persist_failed"

    def test_validation_error_maps_to_422(self, exception_app):
        with TestClient(exception_app) as client:
            response = client.get("/invalid-features")
        assert response.status_code == 422
        assert "NaN" in response.json()["detail"]
