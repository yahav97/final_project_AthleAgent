"""Production risk band cutoffs for API responses.

Aligned with Android UI bands (AthleteDashboardActivity / CoachDashboardActivity):
  Low    — finalRiskScore 0–20   (green)
  Medium — finalRiskScore 21–70  (yellow / orange)
  High   — finalRiskScore 71–100 (red)

Classification uses ``int(probability * 100)`` so boundaries match Kotlin ``toInt()``.

Cutoff values are configured in ``config.settings`` (override via env).
"""

from __future__ import annotations

from config import settings
from schemas.types import RiskLevel


def classify_risk_level(
    probability: float,
    *,
    high: float | None = None,
    medium: float | None = None,
) -> RiskLevel:
    high_cutoff = settings.RISK_HIGH_CUTOFF if high is None else high
    medium_cutoff = settings.RISK_MEDIUM_CUTOFF if medium is None else medium
    pct = int(probability * 100)
    if pct > round(high_cutoff * 100):
        return "High"
    if pct > round(medium_cutoff * 100):
        return "Medium"
    return "Low"
