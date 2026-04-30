"""Create and persist a fixed benchmark holdout set for reproducible evaluation."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd

DEFAULT_HOLDOUT_RATIO = 0.2
DEFAULT_SEED = 42


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a fixed benchmark holdout CSV from athlete_injury_data.csv.")
    parser.add_argument("--holdout-ratio", type=float, default=DEFAULT_HOLDOUT_RATIO)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    dataset_path = script_dir / "athlete_injury_data.csv"
    benchmark_path = script_dir / "benchmark_holdout.csv"
    if benchmark_path.exists() and not args.force:
        print(f"Benchmark already exists: {benchmark_path}")
        return 0
    if not dataset_path.exists():
        raise FileNotFoundError(f"{dataset_path} not found. Run data_generator.py first.")

    df = pd.read_csv(dataset_path)
    if "athlete_id" not in df.columns:
        raise ValueError("athlete_id column is required to build grouped benchmark holdout.")

    athletes = pd.Series(df["athlete_id"].dropna().unique()).sort_values().reset_index(drop=True)
    sample_n = max(1, int(len(athletes) * args.holdout_ratio))
    holdout_ids = athletes.sample(n=sample_n, random_state=args.seed)
    holdout = df[df["athlete_id"].isin(set(holdout_ids.tolist()))].copy()
    holdout = holdout.sort_values(["athlete_id", "date"]).reset_index(drop=True)
    holdout.to_csv(benchmark_path, index=False)
    print(f"Benchmark holdout created: {benchmark_path} (rows={len(holdout)}, athletes={sample_n})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
