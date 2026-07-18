# AthleAgent — Docker (Backend + ML)

Run the FastAPI backend and promoted ML model in a single container. The Android app stays **outside** Docker (emulator or device).

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Mac) or Docker Engine (Linux) — **installed and running**
- Before `docker compose up`, confirm the daemon is up: `docker version` must show a **Server** section (not only Client)
- `backend/firebase-key.json` — Firebase service account (**local only**, not in git; required for Firestore)

## Quick start

From the repository root:

```powershell
# From the repository root (place backend/firebase-key.json first — local only, not in git)
docker compose up --build
```

Verify:

| Check | URL | Expected |
|-------|-----|----------|
| Readiness | http://localhost:8000/health | **200** when Firestore + gated model are live; **503** if either dependency is down |
| Model | http://localhost:8000/status/ml | `"status": "Live"` |
| Pre-demo check | `cd backend && python -m pytest tests/unit/test_model_loader.py::TestPromotedPointerResolution -q` | `3 passed` |
| Full backend suite | `cd backend && python -m pytest tests/ -v` | `252 passed` |
| ML policy / parity | `cd ML_model && python -m pytest tests/ -v` | `12 passed` |

CI runs backend + ML_model pytest on every push/PR that touches `backend/`, `ML_model/`, or `.github/workflows/backend-tests.yml`.

> **Security (demo):** Docker publishes port **8000 on 127.0.0.1 only** — not reachable from other machines on the network. Swagger UI (`/docs`) is disabled when `APP_ENV=demo`.

From the Android emulator (unchanged): `http://10.0.2.2:8000/` — see `ApiClient.kt`.

---

> **Note:** If `backend/firebase-key.json` was missing on a first run, Docker may have created an empty **directory** with that name. Remove it (`Remove-Item -Recurse -Force backend\firebase-key.json` on Windows) and put your Firebase service-account JSON back at `backend/firebase-key.json` before `docker compose up --build` again.

---

## What is in the container

```
/app/
├── backend/              ← uvicorn entry (WORKDIR)
├── ML_model/artifacts/   ← promoted model + manifest
└── logs/                 ← mounted from ./logs on the host
```

The model loads **in-process** at startup (same as local `uvicorn`). No separate ML service.

## Android app

No code changes required. With `127.0.0.1:8000:8000` published on the host, the emulator still reaches the API at `10.0.2.2:8000`.

On the app side:

- `google-services.json` is already under `android_app/AthleAgent/app/`
- `GEMINI_API_KEY` in `local.properties` — required for meal-photo analysis (Gemini Vision); key is provided with the submission (see root README)

## Local development (without Docker)

Still supported — see the root [README.md](../README.md) (local Python section):

```bash
pip install -r backend/requirements.txt
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Updating the model

Training stays **outside** Docker:

```bash
python ML_model/run_pipeline.py
docker compose up --build
```

Optional dev mount (no rebuild after retrain):

```yaml
volumes:
  - ./ML_model/artifacts:/app/ML_model/artifacts:ro
```

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| `dockerDesktopLinuxEngine: The system cannot find the file specified` | Docker Desktop is **not running** — start it from the Start menu and wait until status is **Running**, then retry |
| `ImportError` / xgboost at startup | Image missing `libgomp1` — rebuild with current `Dockerfile` |
| Firestore errors / null client | Missing or invalid `firebase-key.json` |
| `"status": "Blocked"` on `/status/ml` | Manifest gate failed — check `gate_reason` in response |
| Healthcheck unhealthy | Wait for `start_period` (20s); `/health` returns **503** when Firestore or the ML gate is down — check logs: `docker compose logs backend` |

## Related documentation

| Document | Content |
|----------|---------|
| [README.md](../README.md) | Project overview, run, API, tests |
| [docs/HLD.md](HLD.md) | Full project HLD |
| [docs/LLD.md](LLD.md) | Full project LLD |
| [MODEL_SELECTION.md](MODEL_SELECTION.md) | Model selection protocol |
