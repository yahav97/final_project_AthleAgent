"""Domain exceptions and FastAPI handlers for AthleAgent backend."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from utils.logging import logger


class AthleAgentException(Exception):
    """Base domain exception with HTTP status and optional machine-readable code."""

    status_code: int = 500

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


class ValidationError(AthleAgentException):
    """Feature or payload validation failed."""

    status_code = 422


class DatabaseError(AthleAgentException):
    """Firestore or persistence operation failed."""

    status_code = 503


class MLModelError(AthleAgentException):
    """Model artifact missing, blocked by quality gate, or inference unavailable."""

    status_code = 503


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AthleAgentException)
    async def handle_athleagent_exception(
        _request: Request,
        exc: AthleAgentException,
    ) -> JSONResponse:
        logger.warning(
            "domain_error status=%s code=%s message=%s",
            exc.status_code,
            exc.code,
            exc,
            extra={"event": "domain_error"},
        )
        body: dict[str, str] = {"detail": str(exc)}
        if exc.code:
            body["code"] = exc.code
        return JSONResponse(status_code=exc.status_code, content=body)
