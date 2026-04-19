"""Load and expose the sklearn estimator used by prediction routes."""

from __future__ import annotations

import os
from typing import Any, Optional

import joblib

from utils.logging import logger

_estimator: Optional[Any] = None


def load_model(model_path: str | None = None) -> Optional[Any]:
    """Load joblib model from disk. Idempotent: replaces cached estimator."""
    global _estimator
    path = model_path or os.path.join(os.path.dirname(os.path.dirname(__file__)), "injury_model.pkl")
    if os.path.exists(path):
        _estimator = joblib.load(path)
        logger.info("Model loaded successfully from %s", path)
        return _estimator
    logger.warning("Model file not found at %s. Run ML_model/train_model.py first.", path)
    _estimator = None
    return None


def get_model() -> Optional[Any]:
    """Return the cached estimator, or None if not loaded."""
    return _estimator
