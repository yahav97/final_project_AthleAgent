"""Schemas for client observability endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ClientEventType = Literal["error", "screen_view", "user_action", "ml_trigger", "sync"]


class ClientEventIn(BaseModel):
    """Unified client telemetry: errors, navigation, and key user actions."""

    event_type: ClientEventType = Field(default="error")
    level: str = Field(default="ERROR", max_length=16)
    tag: str = Field(..., max_length=64)
    message: str = Field(..., max_length=500)
    request_id: str | None = Field(default=None, max_length=64)
    user_id: str | None = Field(default=None, max_length=128)
    app_version: str | None = Field(default=None, max_length=32)
    timestamp: str | None = Field(default=None, max_length=64)
    screen: str | None = Field(default=None, max_length=128)
