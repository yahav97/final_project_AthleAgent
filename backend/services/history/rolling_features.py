"""Rolling workload/recovery features from merged history rows."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from services.feature_engineering import (
    acwr_baseline_from_weekly_stats,
    acwr_ratio_bounded,
)
from services.field_transforms import (
    daily_distance_km_from_doc,
    hrv_proxy_from_resting_hr,
    resting_hr_from_doc,
)


def sleep_hours(doc: dict[str, Any]) -> float:
    sleep_minutes = float(doc.get("sleepMinutes") or 0.0)
    if sleep_minutes <= 0:
        return 7.0
    return max(3.0, min(12.0, sleep_minutes / 60.0))


def hrv_score(doc: dict[str, Any], resting_hr: float) -> float:
    hrv_rmssd = float(doc.get("hrvRmssd") or 0.0)
    if hrv_rmssd > 0:
        return float(max(30.0, min(105.0, hrv_rmssd)))
    return hrv_proxy_from_resting_hr(resting_hr)


def compute_historical_derived_features(history_rows: list[dict[str, Any]]) -> dict[str, float] | None:
    """Compute weekly-history rolling features from merged historical daily rows."""
    if not history_rows:
        return None

    rows: list[dict[str, float | str]] = []
    for row in history_rows:
        date_key = str(row.get("date_key") or "")
        if not date_key:
            continue
        rest_hr = resting_hr_from_doc(row)
        row_hrv_score = hrv_score(row, rest_hr)
        rows.append(
            {
                "date_key": date_key,
                "daily_distance_km": daily_distance_km_from_doc(row),
                "sleep_hours": sleep_hours(row),
                "hrv_score": row_hrv_score,
            }
        )
    if not rows:
        return None

    frame = pd.DataFrame(rows).sort_values("date_key")
    frame["acute_load_7d"] = frame["daily_distance_km"].rolling(7, min_periods=1).mean()
    weekly_mean = frame["daily_distance_km"].rolling(7, min_periods=1).mean()
    weekly_std = frame["daily_distance_km"].rolling(7, min_periods=1).std().fillna(0.0)
    baseline = pd.Series(
        [
            acwr_baseline_from_weekly_stats(float(mean), float(std))
            for mean, std in zip(weekly_mean, weekly_std, strict=True)
        ],
        index=frame.index,
    )
    frame["acwr_ratio"] = [
        acwr_ratio_bounded(float(acute), float(base))
        for acute, base in zip(frame["acute_load_7d"], baseline, strict=True)
    ]

    frame["sleep_debt_3d"] = (8.0 - frame["sleep_hours"]).rolling(3, min_periods=1).sum()
    frame["hrv_rolling_7d"] = frame["hrv_score"].rolling(7, min_periods=1).mean()
    frame["hrv_drop"] = (frame["hrv_score"] - frame["hrv_rolling_7d"]).clip(lower=-15.0, upper=15.0)

    latest = frame.iloc[-1]
    return {
        "acute_load_7d": float(latest["acute_load_7d"]),
        "acwr_ratio": float(latest["acwr_ratio"]),
        "sleep_debt_3d": float(latest["sleep_debt_3d"]),
        "hrv_drop": float(latest["hrv_drop"]),
    }
