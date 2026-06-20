"""Production risk band cutoffs for API responses.

Aligned with Android UI bands (AthleteDashboardActivity / CoachDashboardActivity):
  Low    — finalRiskScore 0–20   (green)
  Medium — finalRiskScore 21–70  (yellow / orange)
  High   — finalRiskScore 71–100 (red)

Classification uses ``int(probability * 100)`` so boundaries match Kotlin ``toInt()``.
"""

from schemas.types import RiskLevel

RISK_HIGH_CUTOFF = 0.70
RISK_MEDIUM_CUTOFF = 0.20

# Legacy /predict/sklearn uses separate bands (feature-flagged endpoint).
LEGACY_SKLEARN_HIGH = 0.6
LEGACY_SKLEARN_MEDIUM = 0.3


def classify_risk_level(
    probability: float,
    *,
    high: float = RISK_HIGH_CUTOFF,
    medium: float = RISK_MEDIUM_CUTOFF,
) -> RiskLevel:
    pct = int(probability * 100)
    if pct > round(high * 100):
        return "High"
    if pct > round(medium * 100):
        return "Medium"
    return "Low"
