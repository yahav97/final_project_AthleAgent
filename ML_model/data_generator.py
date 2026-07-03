"""
AthleAgent - Synthetic Data Generator for Injury Prediction

CLI entry point — implementation lives in ``generation/``.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ml_dir = str(Path(__file__).resolve().parent)
if _ml_dir not in sys.path:
    sys.path.insert(0, _ml_dir)

from generation.config import (  # noqa: E402
    DAYS_PER_ATHLETE,
    DEFAULT_SEED,
    EXPECTED_DATASET_ROWS,
    NUM_ATHLETES,
)
from generation.postprocess import write_quality_report  # noqa: E402
from generation.simulator import compute_training_reference_features, generate_synthetic_data  # noqa: E402

__all__ = [
    "DAYS_PER_ATHLETE",
    "DEFAULT_SEED",
    "EXPECTED_DATASET_ROWS",
    "NUM_ATHLETES",
    "compute_training_reference_features",
    "generate_synthetic_data",
]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic athlete injury dataset.")
    parser.add_argument("--num-athletes", type=int, default=NUM_ATHLETES)
    parser.add_argument("--days", type=int, default=DAYS_PER_ATHLETE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()

    df = generate_synthetic_data(
        num_athletes=args.num_athletes,
        days_per_athlete=args.days,
        seed=args.seed,
    )
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, "athlete_injury_data.csv")
    df.to_csv(output_path, index=False)
    report_path = write_quality_report(
        df,
        script_dir,
        expected_rows=args.num_athletes * args.days,
    )
    print(f"SUCCESS: Created {output_path}")
    print(f"QUALITY REPORT: {report_path}")
