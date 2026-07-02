# ML model

| Resource | Role |
|----------|------|
| [`docs/MODEL_SELECTION.md`](docs/MODEL_SELECTION.md) | **Selection protocol** — CV, holdout, policy, refit, gates (single narrative) |
| [`notebooks/model_improvement_journey.ipynb`](notebooks/model_improvement_journey.ipynb) | **Live demo** — same functions as `train_model.py` on a CSV subset |
| [`artifacts/promoted.json`](artifacts/promoted.json) | Production model pointer (updated by `run_pipeline.py`) |
| `fixtures/athlete_injury_demo.csv` | **In git** — lean demo CSV for the notebook |
| `data_generator.py` | Builds full `athlete_injury_data.csv` (gitignored, ~1000×365) |
| `policy_config.py` | Selection gates (Recall, FPR, F1, …) — notebook can override live |
| `train_model.py` | Full pipeline → `artifacts/<run_id>/` |
| `validate_metrics.py` | Promotion policy gates |
| `run_pipeline.py` | End-to-end train + validate + promote |

**Production feature contract:** [`backend/docs/FEATURES.md`](../backend/docs/FEATURES.md) · [`backend/services/model_features.py`](../backend/services/model_features.py)

**Serving:** FastAPI backend — local `uvicorn` or Docker ([`docs/DOCKER.md`](../docs/DOCKER.md)). Training runs **outside** the container.

## Selection pipeline (summary)

1. **Athlete CV ×2** — random 20% athlete holdouts (seeds 42, 43) → stability table  
2. **Fixed benchmark holdout** — `benchmark_holdout.csv` → train 5 candidates → `pick_best_model`  
3. **CV agreement warning** — if CV leader ≠ holdout winner  
4. **Full-data refit** — winner retrains on all rows → `injury_model.pkl`  
5. **Promotion** — `validate_metrics.py` on holdout metrics  

Details: [`docs/MODEL_SELECTION.md`](docs/MODEL_SELECTION.md)

## Model candidates

See `MODEL_CANDIDATE_NAMES` in `train_model.py`. Edit the tuple to change candidates project-wide.

## Per-run artifacts

```
ML_model/artifacts/<run_id>/
├── injury_model.pkl
├── run_manifest.json
├── athlete_cv_summary.csv
├── model_comparison.csv
├── threshold_sweep.csv
├── calibration_curve_data.csv
└── …
```

`artifacts/promoted.json` points at the active bundle. After promotion, **restart** the backend so `load_model()` picks up the new pointer.

## Quick commands

```bash
# Full synthetic pipeline + promote
python ML_model/run_pipeline.py

# Check serving status (backend must be running)
curl http://localhost:8000/status/ml
```

**Ops reference:** [`backend/docs/MODEL.md`](../backend/docs/MODEL.md)
