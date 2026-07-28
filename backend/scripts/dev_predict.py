"""
Dev CLI: run injury-risk prediction for one athlete (console only).

Usage:
  cd backend
  python scripts/dev_predict.py
  python scripts/dev_predict.py --date 2026-07-22
  python scripts/dev_predict.py --uid other-athlete --date 2026-07-22
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

DEMO_ATHLETE_ID = "demo-athlete"


def _today_israel() -> str:
    return datetime.now(ZoneInfo("Asia/Jerusalem")).strftime("%Y-%m-%d")


def main() -> int:
    parser = argparse.ArgumentParser(description="Dev prediction for one athlete.")
    parser.add_argument("--uid", default=DEMO_ATHLETE_ID, help=f"Athlete uid (default: {DEMO_ATHLETE_ID})")
    parser.add_argument("--date", default=_today_israel(), help="Prediction day D (yyyy-MM-dd), default: today")
    args = parser.parse_args()

    athlete_id = args.uid.strip()
    date_key = args.date.strip()

    try:
        from config import settings
        from ml.model_loader import load_model
        from services.prediction.service import predict_injury_risk_from_firestore

        load_model(settings.MODEL_PATH)
        result = predict_injury_risk_from_firestore(athlete_id, date_key)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Athlete:               {athlete_id}")
    print(f"date:                  {date_key}")
    print(f"risk_level:            {result['risk_level']}")
    print(f"risk_score:            {result['risk_score']}")
    print(f"prediction_confidence: {result['prediction_confidence']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
