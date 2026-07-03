"""Model candidate catalog for training and notebook demos."""

from __future__ import annotations

from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from training.constants import RANDOM_STATE

MODEL_CANDIDATE_NAMES: tuple[str, ...] = (
    "LogisticRegression",
    "RandomForest",
    "GradientBoosting",
    "XGBoostCalibratedTuned",
    "XGBoostDeep",
)


def model_catalog() -> dict[str, Pipeline | RandomForestClassifier | CalibratedClassifierCV | XGBClassifier]:
    """Return the fixed candidate set used by training, notebook, and pipeline."""
    all_candidates: dict[str, Pipeline | RandomForestClassifier | CalibratedClassifierCV | XGBClassifier] = {
        "LogisticRegression": Pipeline(
            steps=[
                ("scaler", StandardScaler()),
                (
                    "model",
                    LogisticRegression(
                        random_state=RANDOM_STATE,
                        class_weight="balanced",
                        max_iter=3000,
                    ),
                ),
            ]
        ),
        "RandomForest": RandomForestClassifier(
            n_estimators=250,
            max_depth=12,
            random_state=RANDOM_STATE,
            class_weight="balanced_subsample",
            n_jobs=-1,
        ),
        "GradientBoosting": GradientBoostingClassifier(
            random_state=RANDOM_STATE,
            n_estimators=180,
            learning_rate=0.05,
            max_depth=3,
        ),
        "XGBoostCalibratedTuned": CalibratedClassifierCV(
            estimator=XGBClassifier(
                n_estimators=320,
                max_depth=4,
                learning_rate=0.045,
                subsample=0.92,
                colsample_bytree=0.92,
                reg_lambda=1.3,
                scale_pos_weight=2.6,
                eval_metric="logloss",
                random_state=RANDOM_STATE,
                n_jobs=-1,
            ),
            method="sigmoid",
            cv=3,
        ),
        "XGBoostDeep": XGBClassifier(
            n_estimators=520,
            max_depth=7,
            learning_rate=0.028,
            subsample=0.86,
            colsample_bytree=0.82,
            colsample_bylevel=0.82,
            reg_alpha=0.5,
            reg_lambda=2.0,
            min_child_weight=6,
            gamma=0.10,
            eval_metric="logloss",
            random_state=RANDOM_STATE,
            n_jobs=-1,
            scale_pos_weight=2.4,
        ),
    }
    missing = [name for name in MODEL_CANDIDATE_NAMES if name not in all_candidates]
    if missing:
        raise ValueError(f"MODEL_CANDIDATE_NAMES references unknown models: {missing}")
    return {name: all_candidates[name] for name in MODEL_CANDIDATE_NAMES}
