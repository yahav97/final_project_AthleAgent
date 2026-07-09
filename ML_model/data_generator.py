"""Generate synthetic athlete injury dataset."""

from __future__ import annotations

import sys
from pathlib import Path

_ml_dir = str(Path(__file__).resolve().parent)
if _ml_dir not in sys.path:
    sys.path.insert(0, _ml_dir)

from csv_io import save_csv  # noqa: E402
from generation.config import DAYS_PER_ATHLETE, DEFAULT_SEED, NUM_ATHLETES  # noqa: E402
from generation.simulator import generate_synthetic_data  # noqa: E402

OUTPUT_FILENAME = "athlete_injury_data.csv"


def main() -> None:
    df = generate_synthetic_data(
        num_athletes=NUM_ATHLETES,
        days_per_athlete=DAYS_PER_ATHLETE,
        seed=DEFAULT_SEED,
    )
    output_path = Path(__file__).resolve().parent / OUTPUT_FILENAME
    save_csv(df, output_path)
    print(f"SUCCESS: Created {output_path}")


if __name__ == "__main__":
    main()
