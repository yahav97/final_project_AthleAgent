# AthleAgent Backend (RC1)

**Documentation:** [`docs/README.md`](docs/README.md) — what lives where (notebook appendix vs production contracts).

FastAPI backend for injury-risk inference. This service is treated as mission-critical:

- If model gate checks pass, `POST /predict/daily` returns a model-based response.
- If gate checks fail or persistence is unavailable, `POST /predict/daily` returns HTTP **503** with a clear error (validation issues → **422**).

## API Structure

### `POST /predict/daily`

Production inference endpoint (minimal trigger). The backend loads `userId`/`date` docs from Firestore and builds the internal feature payload server-side.

**Request:**
- `userId`, `date` (yyyy-MM-dd)

**Response JSON:**
- `risk_score` (`0..1`, injury positive-class probability)
- `risk_level` (`Low|Medium|High`)
- `prediction_confidence` (`0..100`)

**Android display:** the app does **not** use this HTTP body for UI. It triggers inference via `POST /predict/daily`, then reads **`finalRiskScore`** (0–100) from Firestore `daily_health/{date}`. The API `risk_score` and Firestore `finalRiskScore` are the same value on different scales (`×100`).

### `GET /status/ml`

Internal operational endpoint:
- `status` (`Live|Blocked`)
- `gate_reason`
- `winner`
- `threshold`
- `policy`
- `degraded_rc`

## ML Integration and Manifest Gate

Model loading is handled in `backend/ml/model_loader.py`.

At startup, the backend loads the promoted artifact set from:
- `ML_model/artifacts/promoted.json`

Then it validates `run_manifest.json` before marking model as live:
- Recall hard gate: `Recall@Threshold >= 0.80`
- AUC live sanity gate (RC1): `ROC-AUC >= 0.68`

If gate validation fails:
- model status becomes `Blocked`
- `POST /predict/daily` returns HTTP 503 (no fallback predictions)

## Before You Run (for reviewers)

**Option A — Docker:** see [`docs/DOCKER.md`](../docs/DOCKER.md) (`docker compose up --build` from repo root).

**Option B — Local Python:** install dependencies **once** from the **repository root** (not from `backend/`):

```bash
pip install -r backend/requirements.txt
```

The backend loads a **joblib** bundle whose estimator is **XGBoost** (`XGBoostDeep`). These packages are **required** at the pinned versions in `backend/requirements.txt`:

| Package | Version | Role |
|---------|---------|------|
| `joblib` | `1.5.3` | Load `injury_model.pkl` at startup |
| `scikit-learn` | `1.8.0` | Preprocessing pipeline inside the saved model |
| `xgboost` | `3.1.2` | Classifier used for `/predict/daily` inference |

Promoted model pointer: `ML_model/artifacts/promoted.json`  
After install, verify ML status: `GET http://localhost:8000/status/ml` → expect `"status": "Live"`.

Alternative (same file via root alias): `pip install -r requirements.txt`

## Run with Docker

For reviewers who prefer a one-command setup (backend + promoted model in one container):

See **[`docs/DOCKER.md`](../docs/DOCKER.md)** — requires [Docker Desktop](https://www.docker.com/products/docker-desktop/) **installed and running** (`docker version` must show Server), plus `backend/firebase-key.json`.

```bash
docker compose up --build
```

The local Python workflow below remains fully supported.

## Run Locally

### 1) Create virtual environment

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

### 2) Install dependencies

From the repository root:

```bash
pip install -r backend/requirements.txt
```

### 3) Start backend

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Docs: `http://localhost:8000/docs`

## Tests

Run all backend tests:

```bash
cd backend
python -m pytest tests/ -v
```

Run **unit tests only** (no HTTP / Firestore / real model):

```bash
python -m pytest tests/unit/ -v -m unit
```

Run **integration tests** (FastAPI routes):

```bash
python -m pytest tests/ -v -m integration
```

Shared fixtures live in `tests/conftest.py`. Unit tests are under `tests/unit/`.

## Data storage

- Daily athlete data and prediction outputs are read/written via **Firestore** (see `services/history_service.py`). There is **no** PostgreSQL layer in this backend.
- After `POST /predict/daily`, merged fields on `daily_health/{date}` include **`finalRiskScore`**, **`riskLevel`**, **`predictionConfidence`**, **`predictionUpdatedAt`** (see `save_daily_prediction_result`).

## Notes for Evaluation

- RC1 is promoted through `ML_model/run_pipeline.py`.
- Artifact history is versioned under `ML_model/artifacts/<timestamp>/`.
- Production pointer is `ML_model/artifacts/promoted.json`.
