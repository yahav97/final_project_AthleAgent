# AthleAgent

**Shifting athlete care from reaction to prevention.**

AthleAgent is an Android + FastAPI system that turns daily athlete data (check-ins, Health Connect metrics, meal photos) into a single **Injury Risk Score** (0–100%) for athletes and coaches.

| Layer | Stack |
|-------|--------|
| Android | Kotlin, Activities, View Binding, Retrofit, Firebase Auth, Firestore, Health Connect, Gemini Vision |
| Backend | Python 3.11+, FastAPI, Uvicorn, firebase-admin |
| Data store | **Cloud Firestore** (no local SQL database) |
| ML | XGBoost + scikit-learn (promoted model included under `ML_model/artifacts/`) |

---

## Quick start for evaluators

No `.env` file is required. Defaults in `backend/config.py` are enough to run.

Firestore connection uses the included Firebase Admin key:

| File | Role | Included in this repo? |
|------|------|------------------------|
| `backend/firebase-key.json` | Backend → Firestore (read/write predictions) | **Yes** |
| `android_app/AthleAgent/app/google-services.json` | Android → Firebase Auth + Firestore | **Yes** |
| `.env` | Optional overrides only | **Not needed** |
| `GEMINI_API_KEY` in `local.properties` | Meal photo analysis only | Optional (see below) |

### Step 1 — Start the backend

From the **repository root** (folder that contains `docker-compose.yml`).

**Option A — Docker (recommended)**

1. Install and start [Docker Desktop](https://www.docker.com/products/docker-desktop/).
2. Confirm the engine is up (`docker version` must show **Client** and **Server**).
3. Run:

```powershell
docker compose up --build
```

**Option B — Local Python 3.11+**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

(macOS/Linux: `source .venv/bin/activate` instead of the PowerShell activate line.)

### Step 2 — Verify backend + Firestore

| Check | URL | Expected |
|-------|-----|----------|
| Health | http://localhost:8000/health | HTTP 200 |
| ML model | http://localhost:8000/status/ml | `"status": "Live"` |

If ML is `"Live"`, the promoted model loaded. Firestore uses `backend/firebase-key.json` automatically (no `.env`).

### Step 3 — Run the Android app

1. Open `android_app/AthleAgent` in **Android Studio**.
2. Let Gradle sync (creates `local.properties` with `sdk.dir` on your machine).
3. Run on an **emulator** (default API base URL `http://10.0.2.2:8000/` already points at the host backend).
4. Register / sign in with Firebase Auth, then use athlete or coach flows.

**Optional — meal photo analysis:** copy `local.properties.example` → `local.properties` (keep the `sdk.dir` Android Studio created) and set `GEMINI_API_KEY`. Free key: [Google AI Studio](https://aistudio.google.com/apikey). Injury risk scoring works **without** Gemini.

**Physical device:** change `BASE_URL` in `ApiClient.kt` to your PC’s LAN IP (e.g. `http://192.168.x.x:8000/`).

### Step 4 — Demo flow

1. Backend running, `/status/ml` → `"Live"`.
2. Sign in on the app.
3. **Athlete:** wearable sync / daily check-in → trigger prediction → read risk from Firestore.
4. **Coach:** team dashboard with athlete risk scores.

---

## Repository layout

```
AthleAgent/
├── android_app/AthleAgent/   # Android application
├── backend/                  # FastAPI inference API + firebase-key.json
├── ML_model/                 # Training pipeline + promoted artifacts
├── docs/                     # Design and ops documentation
├── docker-compose.yml
└── README.md
```

---

## Prerequisites

| Component | Requirement |
|-----------|-------------|
| **Android** | [Android Studio](https://developer.android.com/studio) (recent stable), JDK 17 |
| **Device** | Emulator or physical device (API 26+). Health Connect works best on a real device. |
| **Backend** | [Docker Desktop](https://www.docker.com/products/docker-desktop/) **or** Python **3.11+** |

---

## Configuration notes

- **No `.env` required.** Copy `backend/.env.example` → `backend/.env` only if you want to override defaults (ports, risk thresholds, etc.).
- **Firestore** is the database. Credentials are in `backend/firebase-key.json` and `app/google-services.json`.
- **Promoted ML model** is already under `ML_model/artifacts/` — no retraining needed to run.

Full Docker notes: [`docs/DOCKER.md`](docs/DOCKER.md) · Backend details: [`backend/README.md`](backend/README.md)

---

## Optional — retrain the ML model

```bash
pip install -r backend/requirements.txt
python ML_model/run_pipeline.py
```

Restart the backend afterward. See [`ML_model/README.md`](ML_model/README.md).

---

## Backend tests (optional)

```bash
cd backend
python -m pytest tests/ -v
```

---

## ZIP / submission contents

Include source, docs, promoted ML artifacts, and evaluation credentials:

- Include: `backend/firebase-key.json`, `app/google-services.json`, `ML_model/artifacts/`
- Exclude: `**/build/`, `.gradle/`, `.idea/`, `__pycache__/`, `.venv/`, `logs/`, personal `.env`, personal `local.properties`

---

## Documentation index

| Document | Content |
|----------|---------|
| [`docs/HLD_PROJECT.md`](docs/HLD_PROJECT.md) | High-level design |
| [`docs/LLD_PROJECT.md`](docs/LLD_PROJECT.md) | Low-level design |
| [`docs/DOCKER.md`](docs/DOCKER.md) | Docker setup |
| [`docs/NFR.md`](docs/NFR.md) | Non-functional requirements |
| [`backend/README.md`](backend/README.md) | Backend API, config, tests |
| [`backend/docs/RISK_SCORE.md`](backend/docs/RISK_SCORE.md) | Risk score pipeline |
| [`ML_model/README.md`](ML_model/README.md) | Training pipeline and artifacts |

---

## Authors

- **Yahav Simon**
- **Tzuf Feldon**
