# AthleAgent

Android app + FastAPI backend that estimates daily injury risk for athletes (and shows scores to coaches), from check-ins, Health Connect, and optional meal photos.

## Run it

No `.env` needed; defaults in `backend/config.py` are enough.

| Credential | Notes |
| --- | --- |
| `backend/firebase-key.json` | Required for Firestore — place locally (not in the repo) |
| `android_app/.../google-services.json` | Already in the repo |
| `GEMINI_API_KEY` in `local.properties` | Optional; only for meal photos |

### Backend

From the repo root (with [Docker Desktop](https://www.docker.com/products/docker-desktop/) running):

```powershell
docker compose up --build
```

Or locally with Python 3.11+:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Check: [http://localhost:8000/health](http://localhost:8000/health) (readiness — Firestore + live model; **503** if either is down) and [http://localhost:8000/status/ml](http://localhost:8000/status/ml) (`"status": "Live"`).

### Android

1. Open `android_app/AthleAgent` in Android Studio (JDK 17).
2. Run on an emulator (API 26+). Base URL is already `http://10.0.2.2:8000/`.
3. Sign in as athlete or coach.

On a physical device, point `BASE_URL` in `ApiClient.kt` at your PC’s LAN IP.

## Layout

```
android_app/AthleAgent/   Android client
backend/                  FastAPI + tests
ML_model/                 Training + promoted artifacts
docs/                     HLD / LLD / Docker / ML selection
```

## Extra

- Tests: `cd backend && python -m pytest tests/ -v` · ML policy/parity: `cd ML_model && python -m pytest tests/ -v`
- Retrain: `python ML_model/run_pipeline.py`, then restart the backend
- Docker: [docs/DOCKER.md](docs/DOCKER.md)
