"""Unit tests for client telemetry rate limiting."""

from __future__ import annotations

import pytest

from schemas.observability import ClientEventIn
from utils.client_event_limiter import reset_client_event_limiter, should_accept_client_event

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clear_limiter():
    reset_client_event_limiter()
    yield
    reset_client_event_limiter()


class TestClientEventLimiter:
    def test_errors_are_never_rate_limited(self):
        event = ClientEventIn(
            event_type="error",
            tag="ML_Trigger",
            message="failed",
            user_id="u1",
        )
        assert should_accept_client_event(event, "u1") is True
        assert should_accept_client_event(event, "u1") is True

    def test_screen_view_is_deduplicated(self):
        event = ClientEventIn(
            event_type="screen_view",
            level="INFO",
            tag="DailyCheckIn",
            message="screen_opened",
            user_id="u1",
            screen="DailyCheckInActivity",
        )
        assert should_accept_client_event(event, "u1") is True
        assert should_accept_client_event(event, "u1") is False

    def test_different_tags_are_independent(self):
        first = ClientEventIn(
            event_type="screen_view",
            level="INFO",
            tag="Dashboard",
            message="screen_opened",
            user_id="u1",
        )
        second = ClientEventIn(
            event_type="screen_view",
            level="INFO",
            tag="DailyCheckIn",
            message="screen_opened",
            user_id="u1",
        )
        assert should_accept_client_event(first, "u1") is True
        assert should_accept_client_event(second, "u1") is True
