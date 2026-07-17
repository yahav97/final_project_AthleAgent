"""Create a fixed benchmark holdout CSV for reproducible evaluation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

_ml_dir = str(Path(__file__).resolve().parent)
if _ml_dir not in sys.path:
    sys.path.insert(0, _ml_dir)

from training.constants import (  # noqa: E402
    BENCHMARK_RELPATH,
    DATASET_FILENAME,
    RANDOM_STATE,
)

HOLDOUT_RATIO = 0.2


def main() -> int:
    parser = argparse.ArgumentParser(description="Create fixed athlete holdout benchmark CSV.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate even when benchmark file already exists.",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    dataset_path = script_dir / DATASET_FILENAME
    benchmark_path = script_dir / BENCHMARK_RELPATH
    benchmark_path.parent.mkdir(parents=True, exist_ok=True)

    if benchmark_path.exists() and not args.force:
        print(f"Benchmark already exists: {benchmark_path} (use --force to regenerate)")
        return 0
    if not dataset_path.exists():
        raise FileNotFoundError(f"{dataset_path} not found. Run data_generator.py first.")

    df = pd.read_csv(dataset_path)
    if "athlete_id" not in df.columns:
        raise ValueError("athlete_id column is required to build grouped benchmark holdout.")

    athletes = pd.Series(df["athlete_id"].dropna().unique()).sort_values().reset_index(drop=True)
    sample_n = max(1, int(len(athletes) * HOLDOUT_RATIO))
    holdout_ids = athletes.sample(n=sample_n, random_state=RANDOM_STATE)
    holdout = df[df["athlete_id"].isin(set(holdout_ids.tolist()))].copy()
    holdout = holdout.sort_values(["athlete_id", "date"]).reset_index(drop=True)
    holdout.to_csv(benchmark_path, index=False)
    print(f"Benchmark holdout created: {benchmark_path} (rows={len(holdout)}, athletes={sample_n})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
