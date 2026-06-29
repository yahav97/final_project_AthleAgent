"""
Write realistic demo field values to Firestore for one athlete (merge writes).

Intended for the new/updated contract fields:
  - users/{uid}: birth_date, historyInjuryCount
  - daily_health/{date}: sleepMinutes, injuredYesterday, … (today)
  - daily_health/{date-1}: steps, distanceMeters, HR, weight, … (yesterday / physical)
  - daily_checkins/{date}: stress, soreness, energy
  - daily_nutrition/{date}: protein, carbs, mealsLoggedCount
  - daily_health/{date} (optional fake backend outputs): finalRiskScore, riskLevel,
    predictionConfidence, predictionUpdatedAt

Requires the same credentials as the API (config / FIREBASE_SERVICE_ACCOUNT_KEY / backend/firebase-key.json).

  cd backend
  python scripts/seed_demo_athlete_firestore.py --user-id YOUR_FIREBASE_UID

Optional:
  --date YYYY-MM-dd   (default: today in Asia/Jerusalem)
  --dry-run           (print only, no writes)
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from zoneinfo import ZoneInfo

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _today_israel() -> str:
    return datetime.now(ZoneInfo("Asia/Jerusalem")).strftime("%Y-%m-%d")


def _prev_day(date_key: str) -> str:
    d = datetime.strptime(date_key, "%Y-%m-%d").replace(tzinfo=ZoneInfo("Asia/Jerusalem"))
    return (d - timedelta(days=1)).strftime("%Y-%m-%d")


def _get_db():
    from services.history_service import _get_firestore_client

    return _get_firestore_client()


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed demo athlete docs in Firestore (merge).")
    parser.add_argument("--user-id", required=True, help="Firebase Auth uid (users/{uid})")
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Calendar day for prediction (yyyy-MM-dd). Default: today (Israel).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print payloads only; do not write.")
    parser.add_argument(
        "--no-fake-prediction",
        action="store_true",
        help="Do not write simulated prediction fields (finalRiskScore, riskLevel, …).",
    )
    args = parser.parse_args()

    date_key = args.date or _today_israel()
    yesterday_key = _prev_day(date_key)
    now_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    profile: dict[str, Any] = {
        "birth_date": "1995-01-01",
        "historyInjuryCount": 1,
    }

    health_today: dict[str, Any] = {
        "sleepMinutes": 450,
        "lastSync": datetime.now(ZoneInfo("Asia/Jerusalem")).isoformat(),
    }
    if not args.no_fake_prediction:
        # Simulated POST /predict/daily persist (merge) — for UI demos only.
        health_today.update(
            {
                "finalRiskScore": 38.75,
                "riskLevel": "Medium",
                "predictionConfidence": 71.2,
                "predictionUpdatedAt": now_utc,
            }
        )

    health_yesterday: dict[str, Any] = {
        "steps": 9800,
        "distanceMeters": 7800,
        "activeCalories": 420,
        "totalCalories": 2680,
        "heartRateAvg": 58,
        "heartRateMin": 52,
        "heartRateMax": 142,
        "weightKg": 72.5,
        "bmrCalories": 1620,
    }

    checkins: dict[str, Any] = {
        "injuredYesterday": 0,
        "energyLevel": 7,
        "muscleSoreness": 3,
        "stressLevel": 4,
    }

    nutrition: dict[str, Any] = {
        "totalProtein": 130,
        "totalCarbs": 300,
        "mealsLoggedCount": 3,
    }

    paths = {
        f"users/{args.user_id}": profile,
        f"users/{args.user_id}/daily_health/{date_key}": health_today,
        f"users/{args.user_id}/daily_health/{yesterday_key}": health_yesterday,
        f"users/{args.user_id}/daily_checkins/{date_key}": checkins,
        f"users/{args.user_id}/daily_nutrition/{date_key}": nutrition,
    }

    print("Seed demo athlete")
    print(f"  userId={args.user_id}")
    print(f"  date (D)={date_key}  |  yesterday (D-1)={yesterday_key}")
    print()

    if args.dry_run:
        for path, doc in paths.items():
            print(path)
            for k, v in sorted(doc.items()):
                print(f"    {k}: {v}")
            print()
        print("DRY_RUN: no writes performed.")
        return 0

    db = _get_db()
    if db is None:
        print("ERROR: Firestore client not available (check FIREBASE_SERVICE_ACCOUNT_KEY / firebase-key.json).", file=sys.stderr)
        return 1

    user_ref = db.collection("users").document(args.user_id)
    user_ref.set(profile, merge=True)
    user_ref.collection("daily_health").document(date_key).set(health_today, merge=True)
    user_ref.collection("daily_health").document(yesterday_key).set(health_yesterday, merge=True)
    user_ref.collection("daily_checkins").document(date_key).set(checkins, merge=True)
    user_ref.collection("daily_nutrition").document(date_key).set(nutrition, merge=True)

    print("Merge writes OK:")
    for path in paths:
        print(f"  {path}")
    print()
    print("You can call POST /predict/daily with:")
    print(f'  {{"userId": "{args.user_id}", "date": "{date_key}"}}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
