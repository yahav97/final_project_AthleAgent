"""
Export a training CSV from Firestore with **serve parity**:

Same merge policy as ``predict_injury_risk_from_firestore`` (sleep on D;
load from D-1; check-in on D; nutrition from D-1 + server-side backfill).

Labels ``injury_tomorrow`` come from ``injuredYesterday`` on ``daily_checkins/{date+1}``
(legacy fallback: ``daily_health/{date+1}``). Rows without a next-day check-in or
legacy health doc are skipped.

Output columns match ``ML_model/train_model`` expectations: base feature columns
(see ``TRAINING_BASE_FEATURE_COLUMNS``) plus ``athlete_id``, ``date``, ``injury_tomorrow``.
Rolling columns ``acwr_ratio_ma7``, … are omitted here and recomputed by ``train_model``.

Run from repo root or backend (venv with firebase-admin):

  cd backend && python scripts/build_training_dataset_from_firestore.py --output ../ML_model/firestore_training_export.csv
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services.history_service import (
    _get_firestore_client,
    fetch_daily_firestore_snapshot,
    fetch_injury_tomorrow_label,
    stable_athlete_numeric_id,
)
from services.model_features import TRAINING_BASE_FEATURE_COLUMNS
from services.prediction_service import (
    injury_prediction_request_from_firestore_snapshot,
    training_base_feature_dict_from_request,
)


def _parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d")


def _daterange_keys(start: datetime, end: datetime) -> list[str]:
    out: list[str] = []
    d = start.date()
    end_d = end.date()
    while d <= end_d:
        out.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)
    return out


def _list_user_ids(client: Any) -> list[str]:
    return [doc.id for doc in client.collection("users").stream()]


def _iter_daily_health_dates(client: Any, user_id: str) -> list[str]:
    ref = client.collection("users").document(user_id).collection("daily_health")
    keys: list[str] = []
    for doc in ref.stream():
        try:
            _parse_date(doc.id)
        except ValueError:
            continue
        keys.append(doc.id)
    return sorted(keys)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build injury training CSV from Firestore.")
    default_out = Path(__file__).resolve().parents[2] / "ML_model" / "firestore_training_export.csv"
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=default_out,
        help="Destination CSV path (default: <repo>/ML_model/firestore_training_export.csv)",
    )
    parser.add_argument("--start-date", type=str, default=None, help="Inclusive yyyy-MM-dd")
    parser.add_argument("--end-date", type=str, default=None, help="Inclusive yyyy-MM-dd")
    parser.add_argument(
        "--user-ids",
        type=str,
        default=None,
        help="Comma-separated Firebase uids (default: all users collection ids)",
    )
    parser.add_argument(
        "--dates-from-daily-health-only",
        action="store_true",
        help="Only emit rows for dates that have a daily_health doc for that user (within range filter)",
    )
    args = parser.parse_args()

    db = _get_firestore_client()
    if db is None:
        print("Firestore client unavailable (credentials / firebase-admin).", file=sys.stderr)
        return 2

    if args.user_ids:
        user_ids = [u.strip() for u in args.user_ids.split(",") if u.strip()]
    else:
        user_ids = _list_user_ids(db)

    start_dt = _parse_date(args.start_date) if args.start_date else None
    end_dt = _parse_date(args.end_date) if args.end_date else None

    if not args.dates_from_daily_health_only and (start_dt is None or end_dt is None):
        print(
            "Provide both --start-date and --end-date, or pass --dates-from-daily-health-only.",
            file=sys.stderr,
        )
        return 2

    rows: list[dict[str, Any]] = []
    skipped_no_next = 0
    skipped_snapshot = 0

    for uid in user_ids:
        athlete_id = stable_athlete_numeric_id(uid)

        if args.dates_from_daily_health_only:
            date_keys = _iter_daily_health_dates(db, uid)
            if start_dt:
                date_keys = [k for k in date_keys if _parse_date(k).date() >= start_dt.date()]
            if end_dt:
                date_keys = [k for k in date_keys if _parse_date(k).date() <= end_dt.date()]
        else:
            date_keys = _daterange_keys(start_dt, end_dt)

        for date_key in date_keys:
            label = fetch_injury_tomorrow_label(uid, date_key)
            if label is None:
                skipped_no_next += 1
                continue

            snapshot = fetch_daily_firestore_snapshot(uid, date_key)
            if not snapshot:
                skipped_snapshot += 1
                continue

            payload = injury_prediction_request_from_firestore_snapshot(uid, date_key, snapshot)
            feats = training_base_feature_dict_from_request(payload)
            row: dict[str, Any] = {
                "athlete_id": athlete_id,
                "date": date_key,
                **feats,
                "injury_tomorrow": label,
            }
            rows.append(row)

    if not rows:
        print("No rows exported.", file=sys.stderr)
        return 3

    columns = ["athlete_id", "date", *TRAINING_BASE_FEATURE_COLUMNS, "injury_tomorrow"]
    df = pd.DataFrame(rows).loc[:, columns]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    print(
        f"Wrote {len(df)} rows to {args.output} "
        f"(skipped_no_next_day_doc={skipped_no_next}, skipped_empty_snapshot={skipped_snapshot})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
