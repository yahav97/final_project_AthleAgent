"""
Logging configuration for AthleAgent backend.

Supports plain text (legacy) and JSON Lines (production default).
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import settings
from utils.request_context import request_id_var, user_id_var

LOG_DIR = settings.LOG_DIR
LOG_DIR.mkdir(parents=True, exist_ok=True)


class ContextFilter(logging.Filter):
    """Inject request-scoped fields and service metadata into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.user_id = user_id_var.get()
        record.service = settings.PROJECT_NAME
        record.version = settings.VERSION
        if not hasattr(record, "source") or record.source is None:
            record.source = "backend"
        return True


def _build_text_formatter() -> logging.Formatter:
    return logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - "
        "[request_id=%(request_id)s user_id=%(user_id)s] - %(message)s"
    )


def _build_json_formatter() -> logging.Formatter:
    from pythonjsonlogger.json import JsonFormatter

    return JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
    )


def setup_logging(
    log_dir: Path | None = None,
    level: str | None = None,
    log_format: str | None = None,
) -> logging.Logger:
    """Configure the athleagent logger with file rotation and stdout output."""
    resolved_dir = log_dir or settings.LOG_DIR
    resolved_dir.mkdir(parents=True, exist_ok=True)
    resolved_level = (level or settings.LOG_LEVEL).upper()
    resolved_format = (log_format or settings.LOG_FORMAT).lower()

    root = logging.getLogger("athleagent")
    root.setLevel(resolved_level)
    root.handlers.clear()
    root.propagate = False

    formatter: logging.Formatter
    if resolved_format == "json":
        formatter = _build_json_formatter()
    else:
        formatter = _build_text_formatter()

    context_filter = ContextFilter()

    file_handler = RotatingFileHandler(
        resolved_dir / settings.LOG_FILE_NAME,
        maxBytes=settings.LOG_MAX_BYTES,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(context_filter)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(context_filter)

    root.addHandler(file_handler)
    root.addHandler(stream_handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    return root


logger = setup_logging()
