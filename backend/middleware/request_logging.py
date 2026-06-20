"""HTTP request logging middleware with correlation ID support."""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from utils.logging import logger
from utils.request_context import clear_request_context, get_or_create_request_id

SKIP_PATHS = {"/health", "/", "/docs", "/openapi.json", "/redoc", "/status/ml"}
SLOW_MS = 2000


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log completed HTTP requests with smart filtering and X-Request-ID propagation."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        request_id = get_or_create_request_id(request.headers.get("X-Request-ID"))
        start = time.perf_counter()
        status_code = 500
        response: Response | None = None

        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            logger.exception(
                "http_unhandled_error",
                extra={
                    "event": "http_unhandled_error",
                    "source": "backend",
                    "method": request.method,
                    "path": request.url.path,
                },
            )
            raise
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            level = logging.INFO
            if status_code >= 500:
                level = logging.ERROR
            elif status_code >= 400 or duration_ms >= SLOW_MS:
                level = logging.WARNING

            logger.log(
                level,
                "http_request_completed",
                extra={
                    "event": "http_request_completed",
                    "source": "backend",
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )
            clear_request_context()
