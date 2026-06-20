"""Append-only ML operations audit log for training and promotion events."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OPS_LOG = Path(__file__).resolve().parent / "artifacts" / "ops_events.jsonl"


def append_ops_event(event: str, **fields: Any) -> None:
    """Append a single JSON line to the shared ML ops audit log."""
    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }
    OPS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with OPS_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\n")
