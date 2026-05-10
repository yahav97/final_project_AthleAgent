"""Smoke test: lifespan + /health + /docs + /openapi.json + POST /predict/daily (no TCP server)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure backend is on path when run from repo root
BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def main() -> int:
    from fastapi.testclient import TestClient

    from main import app

    with TestClient(app) as client:
        h = client.get("/health")
        assert h.status_code == 200, h.text
        assert h.json().get("status") == "healthy"

        docs = client.get("/docs")
        assert docs.status_code == 200

        spec = client.get("/openapi.json")
        assert spec.status_code == 200
        paths = spec.json().get("paths", {})
        assert "/predict/daily" in paths, "OpenAPI must list /predict/daily"

        payload = {"userId": "smoke_user", "date": "2026-05-09"}
        pr = client.post("/predict/daily", json=payload)
        assert pr.status_code in (200, 500), pr.text
        body = pr.json()
        if pr.status_code == 200:
            assert set(body.keys()) >= {"risk_level", "risk_score", "prediction_confidence"}
        else:
            assert "Prediction unavailable" in body.get("detail", "")

    print(
        "SMOKE_OK",
        json.dumps(
            {
                "health": h.json(),
                "predict_status": pr.status_code,
                "predict_keys": sorted(body.keys()) if pr.status_code == 200 else [],
            }
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
