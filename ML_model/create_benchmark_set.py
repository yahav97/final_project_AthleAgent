"""Create a fixed benchmark holdout CSV for reproducible evaluation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

HOLDOUT_RATIO = 0.2
SEED = 42
DATASET_FILENAME = "athlete_injury_data.csv"
BENCHMARK_FILENAME = "benchmark_holdout.csv"


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    dataset_path = script_dir / DATASET_FILENAME
    benchmark_path = script_dir / BENCHMARK_FILENAME

    if benchmark_path.exists():
        print(f"Benchmark already exists: {benchmark_path}")
        return 0
    if not dataset_path.exists():
        raise FileNotFoundError(f"{dataset_path} not found. Run data_generator.py first.")

    df = pd.read_csv(dataset_path)
    if "athlete_id" not in df.columns:
        raise ValueError("athlete_id column is required to build grouped benchmark holdout.")

    athletes = pd.Series(df["athlete_id"].dropna().unique()).sort_values().reset_index(drop=True)
    sample_n = max(1, int(len(athletes) * HOLDOUT_RATIO))
    holdout_ids = athletes.sample(n=sample_n, random_state=SEED)
    holdout = df[df["athlete_id"].isin(set(holdout_ids.tolist()))].copy()
    holdout = holdout.sort_values(["athlete_id", "date"]).reset_index(drop=True)
    holdout.to_csv(benchmark_path, index=False)
    print(f"Benchmark holdout created: {benchmark_path} (rows={len(holdout)}, athletes={sample_n})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
