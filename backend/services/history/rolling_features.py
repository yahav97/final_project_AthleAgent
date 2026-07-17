"""Rolling workload/recovery features from merged history rows."""

from __future__ import annotations

from typing import Any

import pandas as pd

from config import settings
from services.feature_engineering import (
    acwr_features_from_distance_history,
    sleep_debt_3d_from_sleep_hours,
)
from services.field_transforms import (
    daily_distance_km_from_doc,
    hrv_proxy_from_resting_hr,
    resting_hr_from_doc,
)

HistoricalRollingFeatures = dict[str, float]


def sleep_hours_from_doc(doc: dict[str, Any]) -> float:
    """Sleep duration in hours from a merged history row (defaults to 7h when missing)."""
    sleep_minutes = float(doc.get("sleepMinutes") or 0.0)
    if sleep_minutes <= 0:
        return 7.0
    return max(3.0, min(12.0, sleep_minutes / 60.0))


def hrv_score_from_doc(doc: dict[str, Any], resting_hr: float) -> float:
    """Model HRV score from RMSSD on the doc, or a resting-HR proxy when missing."""
    hrv_rmssd = float(doc.get("hrvRmssd") or 0.0)
    if hrv_rmssd > 0:
        return float(max(30.0, min(105.0, hrv_rmssd)))
    return hrv_proxy_from_resting_hr(resting_hr)


def compute_historical_derived_features(
    history_rows: list[dict[str, Any]],
) -> HistoricalRollingFeatures | None:
    """Compute weekly-history rolling features from merged historical daily rows."""
    if not history_rows:
        return None

    rows: list[dict[str, float | str]] = []
    for row in history_rows:
        date_key = str(row.get("date_key") or "")
        if not date_key:
            continue
        rest_hr = resting_hr_from_doc(row)
        row_hrv_score = hrv_score_from_doc(row, rest_hr)
        rows.append(
            {
                "date_key": date_key,
                "daily_distance_km": daily_distance_km_from_doc(row),
                "sleep_hours": sleep_hours_from_doc(row),
                "hrv_score": row_hrv_score,
            }
        )
    if not rows:
        return None

    # Align windows with ML_model/generation/postprocess.py (7d ACWR, 3d sleep debt).
    frame = pd.DataFrame(rows).sort_values("date_key")
    distances = frame["daily_distance_km"].tolist()
    acute_series: list[float] = []
    acwr_series: list[float] = []
    for index in range(len(distances)):
        acute, acwr = acwr_features_from_distance_history(distances[: index + 1])
        acute_series.append(acute)
        acwr_series.append(acwr)
    frame["acute_load_7d"] = acute_series
    frame["acwr_ratio"] = acwr_series

    sleep_target = float(settings.SLEEP_TARGET_HOURS)
    daily_deficit = (sleep_target - frame["sleep_hours"]).clip(lower=0.0)
    frame["sleep_debt_3d"] = daily_deficit.rolling(3, min_periods=1).sum()
    frame["hrv_rolling_7d"] = frame["hrv_score"].rolling(7, min_periods=1).mean()
    frame["hrv_drop"] = (frame["hrv_score"] - frame["hrv_rolling_7d"]).clip(lower=-15.0, upper=15.0)
    frame["acwr_ratio_ma7"] = frame["acwr_ratio"].rolling(7, min_periods=1).mean()
    frame["sleep_hours_ma7"] = frame["sleep_hours"].rolling(7, min_periods=1).mean()

    latest = frame.iloc[-1]
    return {
        "acute_load_7d": float(latest["acute_load_7d"]),
        "acwr_ratio": float(latest["acwr_ratio"]),
        "acwr_ratio_ma7": float(latest["acwr_ratio_ma7"]),
        "sleep_hours_ma7": float(latest["sleep_hours_ma7"]),
        "sleep_debt_3d": float(latest["sleep_debt_3d"]),
        "hrv_drop": float(latest["hrv_drop"]),
    }
