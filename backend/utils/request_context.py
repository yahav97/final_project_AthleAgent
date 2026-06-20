"""Request-scoped context for correlation IDs and user identity."""

from __future__ import annotations

from contextvars import ContextVar
from uuid import uuid4

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)


def get_or_create_request_id(incoming: str | None) -> str:
    """Return client-supplied or newly generated request ID and store in context."""
    rid = (incoming or "").strip() or str(uuid4())
    request_id_var.set(rid)
    return rid


def clear_request_context() -> None:
    """Reset context vars after a request completes."""
    request_id_var.set(None)
    user_id_var.set(None)
