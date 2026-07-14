# AthleAgent

**Shifting athlete care from reaction to prevention.**

Android + FastAPI system that turns daily athlete signals — check-ins, Health Connect metrics, meal photos — into a single **Injury Risk Score (0–100%)** for athletes and coaches.

| Layer | Stack |
|-------|--------|
| **Android** | Kotlin, Activities, View Binding, Retrofit, Firebase Auth, Firestore, Health Connect, Gemini Vision |
| **Backend** | Python 3.11+, FastAPI, Uvicorn, firebase-admin |
| **Data** | Cloud Firestore (no local SQL) |
| **ML** | XGBoost + scikit-learn — promoted model under `ML_model/artifacts/` |

---

## Quick start (evaluators)

No `.env` file is required. Defaults in `backend/config.py` are enough.

| Credential | Role | In repo? |
|------------|------|----------|
| `backend/firebase-key.json` | Backend ↔ Firestore | **No** — place locally (course hand-off) |
| `android_app/.../google-services.json` | Android ↔ Firebase | **Yes** |
| `GEMINI_API_KEY` in `local.properties` | Meal photo analysis only | Optional |

### 1 — Start the backend

From the **repository root** (folder with `docker-compose.yml`).

**Docker (recommended)**

```powershell
docker compose up --build
```

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/) running (`docker version` must show **Server**).

**Local Python 3.11+**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

(macOS/Linux: `source .venv/bin/activate`)

### 2 — Verify

| Check | URL | Expected |
|-------|-----|----------|
| Health | http://localhost:8000/health | HTTP 200 |
| ML model | http://localhost:8000/status/ml | `"status": "Live"` |
| API docs | http://localhost:8000/docs | Swagger UI |

Firestore uses `backend/firebase-key.json` automatically when present.

### 3 — Run the Android app

1. Open `android_app/AthleAgent` in **Android Studio** (JDK 17).
2. Sync Gradle, run on an **emulator** (API 26+).
3. Emulator API base URL is already `http://10.0.2.2:8000/` in `ApiClient.kt`.
4. Register / sign in → athlete or coach flows.

**Optional — meal photos:** copy `local.properties.example` → `local.properties` (keep `sdk.dir`) and set `GEMINI_API_KEY`. Injury risk works **without** Gemini.

**Physical device:** set `BASE_URL` in `ApiClient.kt` to your PC LAN IP (e.g. `http://192.168.x.x:8000/`).

### 4 — Demo flow

1. Backend up, `/status/ml` → `"Live"`.
2. Sign in on the app.
3. **Athlete:** watch sync + daily check-in → prediction runs → read risk from Firestore.
4. **Coach:** team dashboard with athlete risk scores.

---

## How it works

```
Android (Auth + Health Connect + check-in)
        │  POST /predict/daily  { userId, date }
        ▼
FastAPI  → load Firestore day/history → features → XGBoost
        │  write finalRiskScore, riskLevel, predictionConfidence
        ▼
Firestore daily_health/{date}  ←  Android UI reads score from here
```

- **Risk bands** (must match Android): Low &lt; 20%, Medium 20–70%, High ≥ 70% of probability × 100.
- **ML live gate:** Recall@Threshold ≥ 0.80 and ROC-AUC ≥ 0.68, or `/status/ml` is `Blocked` and predict returns **503**.
- **Confidence (0–100):** blend of history window quality (~60%) and same-day input completeness (~40%).

### Main API

| Endpoint | Purpose |
|----------|---------|
| `POST /predict/daily` | Production inference (`userId` + `date`) |
| `GET /status/ml` | `Live` / `Blocked`, winner, gates |
| `GET /health` | Liveness |

The app **triggers** inference over HTTP, then displays **`finalRiskScore`** from Firestore — not the raw HTTP body.

---

## Repository layout

```
AthleAgent/
├── android_app/AthleAgent/    # Android client
├── backend/                   # FastAPI serving + tests
├── ML_model/                  # Training + promoted artifacts
├── docs/                      # Design docs (optional deep dive)
├── docker-compose.yml
└── README.md                  # ← you are here
```

---

## Configuration

- **No `.env` required.** Override only if needed: copy `backend/.env.example` → `backend/.env`.
- Tunables live in `backend/config.py` (risk bands, history window, confidence weights, logging).
- Promoted model pointer: `ML_model/artifacts/promoted.json` (no retrain needed to demo).

Pinned ML runtime deps (also in `backend/requirements.txt`): `joblib`, `scikit-learn`, `xgboost`.

---

## Optional — retrain ML

```bash
pip install -r backend/requirements.txt
python ML_model/run_pipeline.py
```

Then **restart** the backend so it reloads `promoted.json`.

Pipeline in short: athlete CV → fixed holdout compare (5 candidates) → pick winner by operating-point tiers → refit on full data → `validate_metrics.py` → promote. Demo notebook: `ML_model/notebooks/model_improvement_journey.ipynb`.

---

## Tests

```bash
cd backend
python -m pytest tests/ -v
# unit only:   python -m pytest tests/unit/ -v -m unit
# integration: python -m pytest tests/ -v -m integration
```

CI: `.github/workflows/backend-tests.yml` on changes under `backend/` or promoted artifacts.

---

## Submission / ZIP

**Include:** source, `docs/`, `ML_model/artifacts/`, `google-services.json`  
**Provide separately:** `backend/firebase-key.json` (never commit / never zip for public hand-in)  
**Exclude:** `**/build/`, `.gradle/`, `.idea/`, `__pycache__/`, `.venv/`, `logs/`, personal `.env`, personal `local.properties`, large regenerated CSVs (`athlete_injury_data.csv`)

---

## Further reading (optional)

| Doc | When you need it |
|-----|------------------|
| [`docs/DOCKER.md`](docs/DOCKER.md) | Docker troubleshooting |
| [`docs/HLD_PROJECT.md`](docs/HLD_PROJECT.md) | System architecture |
| [`docs/LLD_PROJECT.md`](docs/LLD_PROJECT.md) | Module-level design |
| [`docs/NFR.md`](docs/NFR.md) | Non-functional requirements |
| [`ML_model/docs/MODEL_SELECTION.md`](ML_model/docs/MODEL_SELECTION.md) | Full selection protocol |
| [`backend/docs/FEATURES.md`](backend/docs/FEATURES.md) | Feature / Firestore contract |

---

## Authors

- **Yahav Simon**
- **Tzuf Feldon**
