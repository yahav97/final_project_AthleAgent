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

## Configuration files

| File | Required | Description |
| --- | --- | --- |
| `backend/firebase-key.json` | Yes | Firebase Admin SDK service-account key (not included in the repository) |
| `android_app/AthleAgent/app/google-services.json` | Yes | Firebase client configuration (included in the repository) |
| `GEMINI_API_KEY` in `local.properties` | No | Required only for meal-photo analysis; see `android_app/AthleAgent/local.properties.example` |

### Obtaining `firebase-key.json`

1. Open the [Firebase Console](https://console.firebase.google.com/) and select the project that matches `google-services.json`.
2. Go to **Project settings** → **Service accounts** → **Generate new private key**.
3. Save the downloaded file as `backend/firebase-key.json`.

## Running the project

### Backend

From the repository root, with Docker Desktop running:

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

1. Open `android_app/AthleAgent` in Android Studio.
2. Allow Gradle sync to complete and install any requested SDK components.
3. Create an emulator with API 26+ (Device Manager), or connect a physical device with USB debugging enabled.
4. Run the application. On the emulator, the backend URL is `http://10.0.2.2:8000/`.
5. Sign in as an athlete or a coach.

For a physical device, set `BASE_URL` in `ApiClient.kt` to the host machine’s LAN address (for example `http://192.168.x.x:8000/`). The device and the host must be on the same network. Prefer the local Python backend (`uvicorn` on `0.0.0.0`) when testing on a physical device, because Docker publishes port 8000 on `127.0.0.1` only.

Optional meal-photo analysis: copy `local.properties.example` to `local.properties` and set `GEMINI_API_KEY`.

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

## Retraining the model (optional)

```powershell
pip install -r backend/requirements.txt
python ML_model/run_pipeline.py
```

Restart the backend afterward (`docker compose up --build` or restart `uvicorn`).

Further Docker documentation: [docs/DOCKER.md](docs/DOCKER.md).
