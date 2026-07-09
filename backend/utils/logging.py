"""
Logging for AthleAgent backend.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import settings
from utils.request_context import request_id_var, user_id_var


class ContextFilter(logging.Filter):
    """Add request id and user id to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.user_id = user_id_var.get()
        record.service = settings.PROJECT_NAME
        record.version = settings.VERSION
        if getattr(record, "source", None) is None:
            record.source = "backend"
        return True


def setup_logging(
    log_dir: Path | None = None,
    level: str | None = None,
    log_to_file: bool | None = None,
) -> logging.Logger:
    """Configure the athleagent logger."""
    resolved_dir = log_dir or settings.LOG_DIR
    resolved_level = (level or settings.LOG_LEVEL).upper()
    write_to_file = settings.LOG_TO_FILE if log_to_file is None else log_to_file

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - "
        "[request_id=%(request_id)s user_id=%(user_id)s] - %(message)s"
    )
    context_filter = ContextFilter()

    root = logging.getLogger("athleagent")
    root.setLevel(resolved_level)
    root.handlers.clear()
    root.propagate = False

    if write_to_file:
        resolved_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            resolved_dir / settings.LOG_FILE_NAME,
            maxBytes=settings.LOG_MAX_BYTES,
            backupCount=settings.LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(context_filter)
        root.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(context_filter)
    root.addHandler(stream_handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    return root


logger = setup_logging()
