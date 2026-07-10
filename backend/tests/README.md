# Backend test layout

Pytest suite for the FastAPI serving layer. Run from `backend/`:

```bash
python -m pytest tests/ -v
python -m pytest tests/unit/ -v -m unit
python -m pytest tests/integration/ -v -m integration
```

## Directory structure

| Path | Scope | What it covers |
|------|-------|----------------|
| `tests/conftest.py` | Shared | Fixtures: `api_client`, Firestore mocks, model bundle, sample requests |
| `tests/unit/` | Pure logic | Preprocessing, prediction orchestration, history, ML gates, schemas |
| `tests/integration/` | HTTP | FastAPI routes, OpenAPI contract, middleware, real-model smoke |

## Unit tests — mirror production modules

| Test file | Production module(s) |
|-----------|---------------------|
| `test_prediction_service.py` | `services/prediction/` (bundle, mapping, orchestration) |
| `test_history_repository.py` | `services/history/` (repository, rolling features, day quality) |
| `test_confidence_fallback.py` | `services/prediction/confidence.py` |
| `test_preprocessing.py` | `services/preprocessing/` (scales, quality score, dataframe) |
| `test_validation.py` | `services/preprocessing/validation.py` |
| `test_field_transforms.py` | `services/field_transforms.py` |
| `test_feature_engineering.py` | `services/feature_engineering.py` |
| `test_model_loader.py` | `ml/model_loader.py` |
| `test_risk_levels.py` | `services/risk_levels.py` (Android band parity) |
| `test_request_features.py` | `services/preprocessing/request_features.py` |
| `test_nutrition_defaults.py` | `services/nutrition_defaults.py` |
| `test_profile_defaults.py` | `services/profile_defaults.py` |
| `test_schemas.py` | `schemas/` (Pydantic validation) |
| `test_exceptions.py` | `utils/exceptions.py` |
| `test_config.py` | `config.py` (cross-module invariants only) |
| `test_client_event_limiter.py` | `utils/client_event_limiter.py` |
| `test_request_context.py` | `utils/request_context.py` |
| `test_feature_type_contract.py` | Integer feature contract + train/serve alignment |

## Integration tests

| Test file | Route / concern |
|-----------|----------------|
| `test_routes_predict_daily.py` | `POST /predict/daily` — validation, success, 503 errors |
| `test_prediction_model_columns.py` | Real `injury_model.pkl` smoke (when artifact present) |
| `test_routes_health.py` | `GET /`, `GET /health` |
| `test_routes_ml_status.py` | `GET /status/ml` |
| `test_openapi_contract.py` | Published API surface |
| `test_request_logging.py` | `X-Request-ID` middleware, client-events rate limit |

## ML training tests

Training pipeline gates and policy live under `ML_model/tests/` (separate from serving).
Serving-side ML gate logic is tested in `tests/unit/test_model_loader.py`.

## Edge-case coverage highlights

- **Firestore unavailable** — empty bundle, persist returns `False`
- **History confidence** — tier boundaries (0/3/4/6/7 quality days)
- **ML manifest gates** — corrupt JSON, missing winner, null recall, recall/AUC below policy
- **Risk bands** — `int(probability * 100)` boundaries matching Android
- **Scale mapping** — `None`, 0, and >100 UI inputs clamped to model scale 1–10
- **ACWR** — capped at 2.8, rest-day floor, zero baseline
