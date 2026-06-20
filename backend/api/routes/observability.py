"""Client observability ingestion routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from config import settings
from schemas.observability import ClientEventIn
from utils.client_event_limiter import should_accept_client_event
from utils.logging import logger
from utils.request_context import get_or_create_request_id, user_id_var

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/observability", tags=["Observability"])


def _client_log_level(event: ClientEventIn) -> int:
    if event.event_type == "error" or event.level.upper() == "ERROR":
        return logging.WARNING
    return logging.INFO


def _resolve_client_key(event: ClientEventIn, request: Request) -> str:
    if event.user_id:
        return event.user_id
    if request.client and request.client.host:
        return f"ip:{request.client.host}"
    return "anonymous"


@router.post("/client-events", status_code=202)
def ingest_client_event(event: ClientEventIn, request: Request) -> dict[str, str | bool]:
    """Accept Android telemetry into the unified system log (202 Accepted)."""
    request_id = get_or_create_request_id(
        request.headers.get("X-Request-ID") or event.request_id
    )
    if event.user_id:
        user_id_var.set(event.user_id)

    client_key = _resolve_client_key(event, request)
    if not should_accept_client_event(event, client_key):
        return {
            "accepted": False,
            "request_id": request_id,
            "reason": "rate_limited",
        }

    logger.log(
        _client_log_level(event),
        "client_event",
        extra={
            "event": "client_event",
            "source": "android",
            "client_event_type": event.event_type,
            "client_level": event.level,
            "client_tag": event.tag,
            "client_message": event.message[:500],
            "client_screen": event.screen,
            "client_app_version": event.app_version,
            "client_timestamp": event.timestamp,
            "request_id": request_id,
            "user_id": event.user_id,
        },
    )
    return {"accepted": True, "request_id": request_id}
