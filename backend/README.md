# AthleAgent backend — ML inference hub

FastAPI service that exposes **injury risk inference** over HTTP. The **system of record** for athlete and team data is **Firestore** (Android app); this backend does not write to Firestore unless you add that later.

**Development branch:** `ml-backend` — keep hub work on this branch until merged to `main`.

**Operational rules**

1. **`android_app/` is read-only** for this backend work — use it only to align JSON field names with Firestore; do not change Kotlin/UI here without explicit approval.
2. **Inference-only default:** set `ENABLE_LEGACY_AUTH_DB=false` (default) so the app starts **without** loading legacy JWT/Postgres auth routes.
3. **Tests:** run `python -m pytest tests/ -v` from this directory before considering changes complete.

---

## Quick start

### 1. Install dependencies

From the repository root:

```bash
pip install -r requirements.txt
```

Or install into a virtual environment of your choice.

### 2. Model artifact (optional but required for real scores)

Train or copy the sklearn model to the backend folder (or set `MODEL_PATH`):

```bash
# After training (ML_model/train_model.py writes here by default):
# backend/injury_model.pkl
```

If the file is missing, `POST /predict` still returns **200** with a small **demo** payload and a note in `recommendation`.

### 3. Run the server

From **`backend/`** (so imports resolve):

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Configuration (environment / `.env`)

| Variable | Default | Purpose |
|----------|---------|---------|
| `ENABLE_LEGACY_AUTH_DB` | `false` | If `true`, mounts legacy `/api/v1/auth/*` routes (Postgres + SQLAlchemy). Keep `false` for the inference hub. |
| `MODEL_PATH` | `backend/injury_model.pkl` (resolved from `config.py`) | Path to the joblib classifier. |
| `DATABASE_URL` | (see `config.py`) | Only used when legacy auth routes are enabled. |
| `SECRET_KEY`, etc. | (see `config.py`) | Legacy auth only. |

Example `.env` for **inference only**:

```env
ENABLE_LEGACY_AUTH_DB=false
MODEL_PATH=C:/dev/final_project_AthleAgent/backend/injury_model.pkl
```

---

## Production HTTP contract: `POST /predict`

**Request:** JSON body with **camelCase** fields aligned with Android / Firestore (all optional; missing values are imputed).

**Response:** JSON

- `risk_level`: `"Low"` | `"Medium"` | `"High"`
- `risk_score`: float in **0–1** (injury class probability from `predict_proba`)
- `recommendation`: short text guidance

### Example: curl (Windows PowerShell)

```powershell
cd backend
curl -s -X POST http://127.0.0.1:8000/predict `
  -H "Content-Type: application/json" `
  -d '{\"userId\":\"demo\",\"date\":\"2026-04-19\",\"sleepMinutes\":420,\"steps\":9000,\"distanceMeters\":7200,\"activeCalories\":550,\"totalCalories\":2600,\"stressLevel\":45,\"muscleSoreness\":3}'
```

### Example: minimal JSON

```json
{
  "sleepMinutes": 480,
  "steps": 8000,
  "stressLevel": 35,
  "muscleSoreness": 2
}
```

### Other routes

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/`, `/health` | Liveness |
| POST | `/predict` | Production pipeline (Firestore-shaped body) |
| POST | `/predict/sklearn` | Legacy **AthleteData** row for the same `.pkl` |
| POST | `/demo_predict` | Heuristic demo (old Android shape) |
| POST | `/test_predict` | Fixed mock for UI tests |
| POST | `/api/v1/auth/*` | **Only if** `ENABLE_LEGACY_AUTH_DB=true` |

---

## Project structure (inference hub)

```
backend/
├── main.py                 # App factory, CORS, routers, startup model load
├── config.py               # Settings including ENABLE_LEGACY_AUTH_DB, MODEL_PATH
├── ml/
│   └── model_loader.py     # joblib load / get_model
├── api/routes/
│   ├── health.py           # GET /, GET /health
│   ├── predict.py          # POST /predict, /predict/sklearn, demo, test
│   └── auth.py             # Legacy; not imported when ENABLE_LEGACY_AUTH_DB=false
├── schemas/
│   ├── inference.py        # InjuryPredictionRequest / Response, AthleteData, …
│   └── user.py             # Legacy auth schemas
├── services/
│   ├── model_features.py   # MODEL_FEATURE_COLUMNS (must match training CSV)
│   ├── preprocessing.py    # Request → model DataFrame
│   ├── feature_engineering.py  # ACWR proxies, sleep debt proxy, etc.
│   ├── prediction_service.py   # predict_proba orchestration
│   └── auth_service.py     # Legacy; unused in inference-only mode
├── tests/
│   ├── test_inference.py
│   ├── test_preprocessing.py
│   └── test_feature_engineering.py
├── database/, models/, repositories/   # Legacy Postgres stack (optional)
└── create_tables.py        # Legacy DB init (optional)
```

---

## Testing

```bash
cd backend
python -m pytest tests/ -v
```

---

## Known limitations

- **Rolling workload:** Training uses true 7d/21d rollups per athlete. The mobile payload is often a **single day**; the service uses **documented proxies** for acute/chronic/ACWR until history is supplied (e.g. extra fields or server-side reads).
- **Legacy stack:** Postgres models and `create_tables.py` remain for optional `ENABLE_LEGACY_AUTH_DB=true` workflows; they are **not** required for `POST /predict`.

---

## API documentation

With the server running: **http://localhost:8000/docs**
