"""Train injury model — entry point for the full training pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

_ml_dir = str(Path(__file__).resolve().parent)
if _ml_dir not in sys.path:
    sys.path.insert(0, _ml_dir)

from training.constants import (  # noqa: E402
    ATHLETE_CV_SPLITS,
    BENCHMARK_FILENAME,
    DATASET_FILENAME,
    LABEL_COLUMN,
    RANDOM_STATE,
    THRESHOLDS_TO_EVAL,
)
from training.models import MODEL_CANDIDATE_NAMES, model_catalog  # noqa: E402
from training.pipeline import (  # noqa: E402
    add_sequential_features,
    assess_cv_holdout_agreement,
    cross_validate_by_athlete,
    load_dataset,
    make_train_split,
    refit_winner_for_serving,
    run_training_pipeline,
    subset_dataset,
    train_and_compare,
)
from training.policy import (  # noqa: E402
    OPERATING_TIER_LABELS,
    add_selection_column,
    build_fixed_threshold_gate_table,
    build_operating_points_table,
    evaluate_with_threshold,
    pick_best_model,
)


def main() -> None:
    run_training_pipeline(verbose=True)


if __name__ == "__main__":
    main()
