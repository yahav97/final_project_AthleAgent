# AthleAgent

Android application and FastAPI backend that estimates daily injury risk for athletes and presents scores to coaches, using daily check-ins, Health Connect data, and optional meal photos.

## Prerequisites

| Tool | Requirement |
| --- | --- |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Required for the Docker-based backend; must be running before `docker compose` |
| [Python](https://www.python.org/downloads/) | 3.11 or newer (local backend / tests without Docker) |
| [Android Studio](https://developer.android.com/studio) | JDK 17 (the JDK bundled with Android Studio is sufficient) |
| Android emulator or device | API level 26 or higher |

A root `.env` file is not required. Default settings in `backend/config.py` are sufficient for a local run.

## Files provided separately (not in the repository)

These secrets are supplied with the project submission (ZIP / private hand-off). Place them as follows before running:

| File / value | Destination | Purpose |
| --- | --- | --- |
| `firebase-key.json` | `backend/firebase-key.json` | Backend → Firestore (Firebase Admin SDK) |
| Gemini API key | `GEMINI_API_KEY=...` in `android_app/AthleAgent/local.properties` | Meal-photo analysis (Gemini Vision) |

`android_app/AthleAgent/app/google-services.json` is already in the repository (Firebase client config for the Android app).

### Setting up the Gemini API key

Meal-photo analysis uses Gemini Vision. The API key is provided with the submission.

1. Open the project in Android Studio so `android_app/AthleAgent/local.properties` is created (or copy from `local.properties.example`).
2. Add the provided key:

```properties
GEMINI_API_KEY=<provided_key>
```

3. Sync Gradle / rebuild the app.

## Running the project

### Backend

1. Place `firebase-key.json` at `backend/firebase-key.json`.
2. From the repository root, with Docker Desktop running:

```powershell
docker compose up --build
```

Alternatively, run locally with Python 3.11+:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Verification:

- http://localhost:8000/health — returns HTTP 200 when Firestore and the ML model are available; HTTP 503 otherwise
- http://localhost:8000/status/ml — response includes `"status": "Live"`

### Android application

1. Place the Gemini API key in `local.properties` as described above.
2. Open `android_app/AthleAgent` in Android Studio.
3. Allow Gradle sync to complete and install any requested SDK components.
4. Create an emulator with API 26+ (Device Manager), or connect a physical device with USB debugging enabled.
5. Run the application. On the emulator, the backend URL is `http://10.0.2.2:8000/`.
6. Sign in as an athlete or a coach.

For a physical device, set `BASE_URL` in `ApiClient.kt` to the host machine’s LAN address (for example `http://192.168.x.x:8000/`). The device and the host must be on the same network. Prefer the local Python backend (`uvicorn` on `0.0.0.0`) when testing on a physical device, because Docker publishes port 8000 on `127.0.0.1` only.

## Project structure

```
android_app/AthleAgent/   Android client
backend/                  FastAPI backend and tests
ML_model/                 Model training and promoted artifacts
docs/                     Design documentation (HLD, LLD, Docker, model selection)
```

## Tests

| Suite | Command | Approximate count |
| --- | --- | --- |
| Backend | `cd backend && python -m pytest tests/ -v` | 252 |
| ML policy / parity | `cd ML_model && python -m pytest tests/ -v` | 12 |

Continuous integration: [`.github/workflows/backend-tests.yml`](.github/workflows/backend-tests.yml) runs both suites when `backend/`, `ML_model/`, or the workflow file change.

Test layout: `backend/tests/unit/`, `backend/tests/integration/`, `ML_model/tests/`.

Further Docker documentation: [docs/DOCKER.md](docs/DOCKER.md).
