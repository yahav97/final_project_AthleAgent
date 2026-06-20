# AthleAgent — Docker (Backend + ML)

Run the FastAPI backend and promoted ML model in a single container. The Android app stays **outside** Docker (emulator or device).

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Mac) or Docker Engine (Linux) — **installed and running**
- Before `docker compose up`, confirm the daemon is up: `docker version` must show a **Server** section (not only Client)
- `backend/firebase-key.json` — Firebase service account (not in git; get from the team or Firebase Console)

## Quick start

From the repository root:

```powershell
# 1. Place the Firebase key BEFORE first compose up (see warning below)
copy path\to\your-key.json backend\firebase-key.json

# 2. Build and run
docker compose up --build
```

Verify:

| Check | URL | Expected |
|-------|-----|----------|
| Liveness | http://localhost:8000/health | 200 OK |
| Model | http://localhost:8000/status/ml | `"status": "Live"` |
| API docs | http://localhost:8000/docs | Swagger UI |

From the Android emulator (unchanged): `http://10.0.2.2:8000/` — see `ApiClient.kt`.

---

> **Important — `firebase-key.json` must exist before `docker compose up`**
>
> Copy `firebase-key.json` into `backend/` **before** the first run.
>
> If you ran `docker compose up` without the file, Docker may create an **empty directory** named `backend/firebase-key.json` on the host. The backend will then fail to parse credentials.
>
> **Fix:**
> 1. Stop containers: `docker compose down`
> 2. Remove the wrong path:
>    - Windows: `Remove-Item -Recurse -Force backend\firebase-key.json`
>    - Mac/Linux: `rm -rf backend/firebase-key.json`
> 3. Copy the real JSON file to `backend/firebase-key.json`
> 4. Run again: `docker compose up --build`

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

No code changes required. With `8000:8000` published on the host, the emulator reaches the API at `10.0.2.2:8000`.

You still need on the app side (as today):

- `google-services.json` in `android_app/AthleAgent/app/`
- `GEMINI_API_KEY` in `local.properties`

## Local development (without Docker)

Still supported — see [backend/README.md](../backend/README.md):

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
| Healthcheck unhealthy | Wait for `start_period` (20s); check logs: `docker compose logs backend` |

## Related documentation

| Document | Content |
|----------|---------|
| [README.md](../README.md) | Project overview + getting started |
| [backend/README.md](../backend/README.md) | API, tests, local Python run |
| [backend/docs/HLD.md](../backend/docs/HLD.md) | Backend architecture |
| [backend/docs/MODEL.md](../backend/docs/MODEL.md) | ML gates, promotion, restart after retrain |
| [docs/HLD_PROJECT.md](HLD_PROJECT.md) | Full project HLD |
| [docs/NFR.md](NFR.md) | NFR-MAINT-03 — modular deployment |
