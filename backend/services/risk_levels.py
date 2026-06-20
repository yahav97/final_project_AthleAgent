"""Production risk band cutoffs for API responses."""

from schemas.types import RiskLevel

RISK_HIGH_CUTOFF = 0.70
RISK_MEDIUM_CUTOFF = 0.40

# Legacy /predict/sklearn uses separate bands (feature-flagged endpoint).
LEGACY_SKLEARN_HIGH = 0.6
LEGACY_SKLEARN_MEDIUM = 0.3


def classify_risk_level(
    probability: float,
    *,
    high: float = RISK_HIGH_CUTOFF,
    medium: float = RISK_MEDIUM_CUTOFF,
) -> RiskLevel:
    if probability >= high:
        return "High"
    if probability >= medium:
        return "Medium"
    return "Low"
