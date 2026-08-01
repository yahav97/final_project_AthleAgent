"""Pure unit tests for request correlation ID helpers."""

from __future__ import annotations

import logging

import pytest

from utils.logging import ContextFilter
from utils.request_context import clear_request_context, get_or_create_request_id, request_id_var

pytestmark = pytest.mark.unit


class TestRequestContext:
    def setup_method(self) -> None:
        clear_request_context()

    def teardown_method(self) -> None:
        clear_request_context()

    def test_get_or_create_request_id_uses_client_value(self):
        rid = get_or_create_request_id("client-abc-123")
        assert rid == "client-abc-123"
        assert request_id_var.get() == "client-abc-123"

    def test_get_or_create_request_id_generates_uuid_when_missing(self):
        rid = get_or_create_request_id(None)
        assert rid
        assert len(rid) == 36

    def test_context_filter_creates_default_request_id_when_missing(self):
        record = logging.LogRecord(
            name="athleagent",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="test",
            args=(),
            exc_info=None,
        )
        assert ContextFilter().filter(record) is True
        assert record.request_id
        assert len(record.request_id) == 36
        assert request_id_var.get() == record.request_id
