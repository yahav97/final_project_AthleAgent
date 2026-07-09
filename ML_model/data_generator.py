"""Generate synthetic athlete injury dataset."""

from __future__ import annotations

import sys
from pathlib import Path

_ml_dir = str(Path(__file__).resolve().parent)
if _ml_dir not in sys.path:
    sys.path.insert(0, _ml_dir)

from generation.config import DAYS_PER_ATHLETE, DEFAULT_SEED, NUM_ATHLETES  # noqa: E402
from generation.simulator import generate_synthetic_data  # noqa: E402
from training.constants import DATASET_FILENAME  # noqa: E402


def main() -> None:
    df = generate_synthetic_data(
        num_athletes=NUM_ATHLETES,
        days_per_athlete=DAYS_PER_ATHLETE,
        seed=DEFAULT_SEED,
    )
    output_path = Path(__file__).resolve().parent / DATASET_FILENAME
    df.to_csv(output_path, index=False)
    print(f"SUCCESS: Created {output_path}")


if __name__ == "__main__":
    main()
