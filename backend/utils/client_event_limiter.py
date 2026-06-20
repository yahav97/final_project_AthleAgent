"""In-memory rate limiting for client telemetry ingestion."""

from __future__ import annotations

import time
from threading import Lock

from config import settings
from schemas.observability import ClientEventIn, ClientEventType

_lock = Lock()
_last_seen: dict[str, float] = {}


def _rate_limit_seconds(event_type: ClientEventType) -> int:
    if event_type == "error":
        return 0
    if event_type == "screen_view":
        return settings.CLIENT_EVENT_RATE_LIMIT_SCREEN_SEC
    if event_type == "user_action":
        return settings.CLIENT_EVENT_RATE_LIMIT_ACTION_SEC
    if event_type == "sync":
        return settings.CLIENT_EVENT_RATE_LIMIT_SYNC_SEC
    if event_type == "ml_trigger":
        return settings.CLIENT_EVENT_RATE_LIMIT_ML_TRIGGER_SEC
    return settings.CLIENT_EVENT_RATE_LIMIT_ACTION_SEC


def should_accept_client_event(event: ClientEventIn, client_key: str) -> bool:
    """
    Return True if the event should be written to the unified log.

    Errors are always accepted. Other types are deduplicated by client_key + type + tag.
    """
    interval = _rate_limit_seconds(event.event_type)
    if interval <= 0:
        return True

    dedupe_key = f"{client_key}:{event.event_type}:{event.tag}"
    now = time.monotonic()
    with _lock:
        previous = _last_seen.get(dedupe_key)
        if previous is not None and (now - previous) < interval:
            return False
        _last_seen[dedupe_key] = now
    return True


def reset_client_event_limiter() -> None:
    """Clear rate-limit state (for tests)."""
    with _lock:
        _last_seen.clear()
