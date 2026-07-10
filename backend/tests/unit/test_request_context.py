"""Pure unit tests for request correlation ID helpers."""

from __future__ import annotations

import pytest

from utils.request_context import get_or_create_request_id, request_id_var

pytestmark = pytest.mark.unit


class TestRequestContext:
    def test_get_or_create_request_id_uses_client_value(self):
        rid = get_or_create_request_id("client-abc-123")
        assert rid == "client-abc-123"
        assert request_id_var.get() == "client-abc-123"

    def test_get_or_create_request_id_generates_uuid_when_missing(self):
        rid = get_or_create_request_id(None)
        assert rid
        assert len(rid) == 36
