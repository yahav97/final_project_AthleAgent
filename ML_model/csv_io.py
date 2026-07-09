"""CSV helpers for ML artifacts and datasets."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def save_csv(df: pd.DataFrame, path: str | Path, *, index: bool = False) -> None:
    """Write a DataFrame to CSV without a trailing blank line in editors."""
    path = Path(path)
    csv_content = df.to_csv(index=index, lineterminator="\n").rstrip("\n")
    path.write_bytes(csv_content.encode("utf-8"))
