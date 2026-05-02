"""Project maintenance cleanup utility for Python cache and old logs.

Usage:
    python clean_logs.py
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LOG_RETENTION_DAYS = 7


def _remove_pyc_files(root: Path) -> int:
    removed = 0
    for path in root.rglob("*.pyc"):
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    return removed


def _remove_pycache_dirs(root: Path) -> int:
    removed = 0
    for path in root.rglob("__pycache__"):
        if path.is_dir():
            try:
                shutil.rmtree(path, ignore_errors=True)
                removed += 1
            except OSError:
                pass
    return removed


def _remove_old_logs(root: Path, days: int) -> int:
    removed = 0
    cutoff = time.time() - days * 24 * 60 * 60
    for path in root.rglob("*.log"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            pass
    return removed


def main() -> int:
    pyc_removed = _remove_pyc_files(ROOT)
    pycache_removed = _remove_pycache_dirs(ROOT)
    logs_removed = _remove_old_logs(ROOT, LOG_RETENTION_DAYS)
    print(
        f"Cleanup completed. Removed: {pyc_removed} .pyc files, "
        f"{pycache_removed} __pycache__ directories, {logs_removed} old log files."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
