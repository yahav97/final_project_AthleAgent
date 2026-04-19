"""Smoke test: lifespan + /health + /docs + /openapi.json + POST /predict (no TCP server)."""

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
        assert "/predict" in paths, "OpenAPI must list /predict"

        payload = {
            "sleepMinutes": 480,
            "steps": 8000,
            "stressLevel": 35,
            "muscleSoreness": 2,
        }
        pr = client.post("/predict", json=payload)
        assert pr.status_code == 200, pr.text
        body = pr.json()
        assert set(body.keys()) >= {"risk_level", "risk_score", "recommendation"}

    print("SMOKE_OK", json.dumps({"health": h.json(), "predict_keys": sorted(body.keys())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
