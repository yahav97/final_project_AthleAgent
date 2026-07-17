"""Verify published OpenAPI surface matches documented production routes."""

import pytest

pytestmark = pytest.mark.integration

DOCUMENTED_PATHS = {
    "/",
    "/health",
    "/predict/daily",
    "/status/ml",
    "/api/v1/observability/client-events",
}


class TestOpenApiContract:
    def test_openapi_json_lists_all_documented_routes(self, api_client):
        response = api_client.get("/openapi.json")
        assert response.status_code == 200

        paths = set(response.json().get("paths", {}).keys())
        missing = DOCUMENTED_PATHS - paths
        assert not missing, f"Missing paths in OpenAPI: {missing}"

    @pytest.mark.parametrize("path,method", [
        ("/health", "get"),
        ("/predict/daily", "post"),
        ("/status/ml", "get"),
        ("/api/v1/observability/client-events", "post"),
    ])
    def test_production_paths_have_operation_metadata(self, api_client, path, method):
        spec = api_client.get("/openapi.json").json()
        operation = spec["paths"][path][method]
        assert operation.get("responses")
        assert "200" in operation["responses"] or "422" in operation["responses"] or "503" in operation["responses"]
