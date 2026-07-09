"""Train injury model — entry point for the full training pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

_ml_dir = str(Path(__file__).resolve().parent)
if _ml_dir not in sys.path:
    sys.path.insert(0, _ml_dir)

from training.pipeline import run_training_pipeline  # noqa: E402


def main() -> None:
    run_training_pipeline(verbose=True)


if __name__ == "__main__":
    main()
