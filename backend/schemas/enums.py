"""Domain enums for fixed vocabularies (replacing scattered string literals)."""

from __future__ import annotations

from enum import Enum


class HistoryConfidence(str, Enum):
    """Rolling-window data quality for historical feature enrichment."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ModelGateReason(str, Enum):
    """Why the promoted model bundle is blocked or allowed."""

    NONE = "none"
    MODEL_NOT_LOADED = "model_not_loaded"
    MODEL_FILE_NOT_FOUND = "model_file_not_found"
    MANIFEST_NOT_FOUND = "manifest_not_found"
    MANIFEST_CORRUPTED = "manifest_corrupted"
    MANIFEST_MISSING_WINNER = "manifest_missing_winner"
    MANIFEST_INVALID_RECALL = "manifest_invalid_recall"
    MANIFEST_INVALID_AUC = "manifest_invalid_auc"
    MANIFEST_RECALL_BELOW_HARD_GATE = "manifest_recall_below_hard_gate"
    MANIFEST_AUC_TOO_LOW = "manifest_auc_too_low"
    MANIFEST_INVALID_POLICY_RECALL_HARD_MIN = "manifest_invalid_policy_recall_hard_min"
    MANIFEST_RECALL_BELOW_POLICY_HARD_MIN = "manifest_recall_below_policy_hard_min"
    FALLBACK_BUNDLE_INVALID = "fallback_bundle_invalid"
    UNSUPPORTED_MODEL_FORMAT = "unsupported_model_format"
    MISSING_ESTIMATOR = "missing_estimator"
    MISSING_FEATURE_COLUMNS = "missing_feature_columns"
    INVALID_THRESHOLD = "invalid_threshold"
    INVALID_MEDIUM_THRESHOLD = "invalid_medium_threshold"


class ModelLiveStatus(str, Enum):
    """Operational ML status exposed by /status/ml."""

    LIVE = "Live"
    BLOCKED = "Blocked"


class BundleResolutionMode(str, Enum):
    """How resolve_model_bundle classified the loaded artifact."""

    FALLBACK_DEMO = "fallback_demo"


class HealthStatus(str, Enum):
    """Health probe responses (values preserved for API compatibility)."""

    OK = "ok"
    HEALTHY = "healthy"
