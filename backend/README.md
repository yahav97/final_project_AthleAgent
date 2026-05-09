# AthleAgent Backend (RC1)

FastAPI backend for injury-risk inference. This service is treated as mission-critical:

- If model gate checks pass, `/predict` returns a model-based response.
- If gate checks fail or input is invalid, `/predict` returns HTTP 500 with a clear error.

## API Structure

### `POST /predict`

Production inference endpoint.

**Request (camelCase, Firestore-shaped):**
- `userId`, `date`
- health/checkin/nutrition fields (optional but quality affects inference)

**Response JSON:**
- `risk_score` (`0..1`)
- `risk_level` (`Low|Medium|High`)
- `recommendation`
- `data_quality_score`
- `data_quality_status`
- `meta`
  - `model_version`
  - `fallback_reason` (`none` for live inference)
  - `confidence_bucket` (`Low|Medium|High`)

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
- Recall hard gate: `Recall@Threshold >= 0.85`
- AUC live sanity gate (RC1): `ROC-AUC >= 0.60`

If gate validation fails:
- model status becomes `Blocked`
- `/predict` returns HTTP 500 (no fallback predictions)

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

```bash
pip install -r requirements.txt
```

### 3) Start backend

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Docs: `http://localhost:8000/docs`

## Tests

Run backend tests:

```bash
cd backend
python -m pytest tests/ -v
```

## Data storage

- Daily athlete data and prediction outputs are read/written via **Firestore** (see `services/history_service.py`). There is **no** PostgreSQL layer in this backend.
- After `POST /predict` or `POST /predict/daily`, the API response field `recommendation` is persisted on the same day’s `daily_health` document as **`backendRecommendation`**.

## Notes for Evaluation

- RC1 is promoted through `ML_model/run_pipeline.py`.
- Artifact history is versioned under `ML_model/artifacts/<timestamp>/`.
- Production pointer is `ML_model/artifacts/promoted.json`.
