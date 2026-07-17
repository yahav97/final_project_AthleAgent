"""
Write demo field values to Firestore for one athlete (merge writes).

Usage:
  cd backend
  python scripts/seed_demo_athlete_firestore.py YOUR_FIREBASE_UID
  python scripts/seed_demo_athlete_firestore.py YOUR_FIREBASE_UID 2026-07-09
"""

from __future__ import annotations

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
    from services.history.firestore_io import get_firestore_client

    return get_firestore_client()


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/seed_demo_athlete_firestore.py USER_ID [YYYY-MM-DD]", file=sys.stderr)
        return 1

    user_id = sys.argv[1].strip()
    date_key = sys.argv[2].strip() if len(sys.argv) > 2 else _today_israel()
    yesterday_key = _prev_day(date_key)
    now_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    profile: dict[str, Any] = {
        "birth_date": "1995-01-01",
        "historyInjuryCount": 1,
    }

    health_today: dict[str, Any] = {
        "sleepMinutes": 450,
        "lastSync": datetime.now(ZoneInfo("Asia/Jerusalem")).isoformat(),
        "finalRiskScore": 38.75,
        "riskLevel": "Medium",
        "predictionConfidence": 71.2,
        "predictionUpdatedAt": now_utc,
    }

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
        f"users/{user_id}": profile,
        f"users/{user_id}/daily_health/{date_key}": health_today,
        f"users/{user_id}/daily_health/{yesterday_key}": health_yesterday,
        f"users/{user_id}/daily_checkins/{date_key}": checkins,
        f"users/{user_id}/daily_nutrition/{date_key}": nutrition,
    }

    print("Seed demo athlete")
    print(f"  userId={user_id}")
    print(f"  date (D)={date_key}  |  yesterday (D-1)={yesterday_key}")
    print()

    db = _get_db()
    if db is None:
        print(
            "ERROR: Firestore client not available (place firebase-key.json in backend/).",
            file=sys.stderr,
        )
        return 1

    user_ref = db.collection("users").document(user_id)
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
    print(f'  {{"userId": "{user_id}", "date": "{date_key}"}}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
