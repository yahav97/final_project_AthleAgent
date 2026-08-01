"""
Seed fixed demo athlete with 7 days of history (overwrites existing data).

Writes wearable/check-in/nutrition data for D-7 … D, then runs production inference
for prior wake-up days (D-7 … D-1) and persists finalRiskScore / riskLevel /
predictionConfidence — same fields as POST /predict/daily.
Day D is left without a score so scripts/dev_predict.py (or the API) can run it live.

Usage:
  cd backend
  python scripts/seed_demo_athlete.py
  python scripts/dev_predict.py
  python scripts/seed_demo_athlete.py --date 2026-07-22
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

DEMO_TEAM_ID = "demo-team"
DEMO_TEAM_CODE = "ATHLEDEMO"
DEMO_COACH_ID = "demo-coach"
DEMO_ATHLETE_ID = "demo-athlete"

# Wake-up day profile: load (prior day) + sleep + survey for each of D-7 … D.
_DAY_PROFILES: list[dict[str, int]] = [
    {"steps": 6000, "distance": 4800, "active_cal": 380, "total_cal": 2400, "sleep": 450, "soreness": 2, "stress": 3, "energy": 8},
    {"steps": 4000, "distance": 3200, "active_cal": 280, "total_cal": 2200, "sleep": 480, "soreness": 1, "stress": 2, "energy": 9},
    {"steps": 8500, "distance": 6800, "active_cal": 520, "total_cal": 2600, "sleep": 420, "soreness": 3, "stress": 4, "energy": 7},
    {"steps": 12000, "distance": 9600, "active_cal": 720, "total_cal": 2900, "sleep": 390, "soreness": 5, "stress": 5, "energy": 6},
    {"steps": 5500, "distance": 4400, "active_cal": 350, "total_cal": 2350, "sleep": 450, "soreness": 4, "stress": 4, "energy": 7},
    {"steps": 9000, "distance": 7200, "active_cal": 550, "total_cal": 2650, "sleep": 420, "soreness": 3, "stress": 4, "energy": 7},
    {"steps": 11500, "distance": 9200, "active_cal": 680, "total_cal": 2850, "sleep": 360, "soreness": 6, "stress": 6, "energy": 5},
    {"steps": 8000, "distance": 6400, "active_cal": 480, "total_cal": 2550, "sleep": 330, "soreness": 7, "stress": 7, "energy": 4},
]


def _today_israel() -> str:
    return datetime.now(ZoneInfo("Asia/Jerusalem")).strftime("%Y-%m-%d")


def _offset_day(date_key: str, days: int) -> str:
    base = datetime.strptime(date_key, "%Y-%m-%d").replace(tzinfo=ZoneInfo("Asia/Jerusalem"))
    return (base + timedelta(days=days)).strftime("%Y-%m-%d")


def _physical_doc(profile: dict[str, int]) -> dict[str, Any]:
    """Wearable load fields for one calendar day."""
    return {
        "steps": profile["steps"],
        "distanceMeters": profile["distance"],
        "activeCalories": profile["active_cal"],
        "totalCalories": profile["total_cal"],
        "heartRateAvg": 58,
        "heartRateMin": 52,
        "heartRateMax": 142,
        "restingHeartRate": 52,
        "hrvRmssd": 62.0,
        "bmrCalories": 1620,
        "weightKg": 72.5,
    }


def _nutrition_doc(day_index: int) -> dict[str, Any]:
    return {
        "totalProtein": 125 + day_index,
        "totalCarbs": 290 + day_index * 5,
        "mealsLoggedCount": 3,
        "totalCalories": 2500 + day_index * 20,
    }


def _get_db():
    from services.history.firestore_io import get_firestore_client

    return get_firestore_client()


def _seed_historical_predictions(athlete_id: str, date_key: str) -> list[dict[str, Any]]:
    """Run production inference for D-7 … D-1 and persist scores (skip day D)."""
    from config import settings
    from ml.model_loader import load_model
    from services.history.persist import save_daily_prediction_result
    from services.prediction.service import predict_injury_risk_from_firestore

    load_model(settings.MODEL_PATH)

    saved: list[dict[str, Any]] = []
    for index in range(7):
        wake_day = _offset_day(date_key, index - 7)
        result = predict_injury_risk_from_firestore(athlete_id, wake_day)
        save_daily_prediction_result(athlete_id, wake_day, result)
        saved.append({"date": wake_day, **result})
    return saved


def seed_demo_athlete(date_key: str) -> list[dict[str, Any]]:
    """Upsert fixed demo athlete, overwrite history, run predictions for D-7 … D-1."""
    from firebase_admin import firestore as fa_firestore

    db = _get_db()
    if db is None:
        raise RuntimeError("Firestore unavailable — place firebase-key.json in backend/.")

    athlete_id = DEMO_ATHLETE_ID
    now_local = datetime.now(ZoneInfo("Asia/Jerusalem")).isoformat()

    team_ref = db.collection("teams").document(DEMO_TEAM_ID)
    team_ref.set(
        {
            "TeamName": "Demo Team",
            "teamCode": DEMO_TEAM_CODE,
            "coachId": DEMO_COACH_ID,
        },
        merge=True,
    )
    team_ref.update({"athletes": fa_firestore.ArrayUnion([athlete_id])})

    user_ref = db.collection("users").document(athlete_id)
    user_ref.set(
        {
            "fullName": "Demo Athlete",
            "role": "Athlete",
            "birth_date": "1998-03-15",
            "historyInjuryCount": 1,
            "email": "demo.athlete@athleagent.dev",
            "teamId": DEMO_TEAM_ID,
        },
        merge=True,
    )

    health_ref = user_ref.collection("daily_health")
    checkin_ref = user_ref.collection("daily_checkins")
    nutrition_ref = user_ref.collection("daily_nutrition")

    for index, profile in enumerate(_DAY_PROFILES):
        wake_day = _offset_day(date_key, index - 7)
        load_day = _offset_day(wake_day, -1)

        if profile["steps"] > 0:
            health_ref.document(load_day).set(_physical_doc(profile), merge=True)

        health_ref.document(wake_day).set(
            {"sleepMinutes": profile["sleep"], "lastSync": now_local},
            merge=True,
        )
        checkin_ref.document(wake_day).set(
            {
                "injuredYesterday": 0,
                "energyLevel": profile["energy"],
                "muscleSoreness": profile["soreness"],
                "stressLevel": profile["stress"],
            },
            merge=True,
        )

    for index in range(7):
        nutrition_day = _offset_day(date_key, index - 7)
        nutrition_ref.document(nutrition_day).set(_nutrition_doc(index), merge=True)

    return _seed_historical_predictions(athlete_id, date_key)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed fixed demo athlete with 7-day history.")
    parser.add_argument("--date", default=_today_israel(), help="Prediction day D (yyyy-MM-dd)")
    args = parser.parse_args()

    try:
        predictions = seed_demo_athlete(args.date.strip())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Athlete: {DEMO_ATHLETE_ID}  |  date={args.date}")
    print("Data seeded for D-7 … D; historical predictions saved for D-7 … D-1:")
    for row in predictions:
        score_pct = round(float(row["risk_score"]) * 100, 2)
        print(
            f"  {row['date']}: {row['risk_level']} ({score_pct}%) "
            f"confidence={row['prediction_confidence']}"
        )
    print(f"Day D ({args.date}) has inputs only — run: python scripts/dev_predict.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
