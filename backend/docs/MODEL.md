# ML model — production reference

> **Full selection narrative** (CV, holdout, policy tiers, refit, deferred ideas):  
> [`ML_model/docs/MODEL_SELECTION.md`](../../ML_model/docs/MODEL_SELECTION.md)  
>
> **Live demo** (same code path on a subset):  
> [`ML_model/notebooks/model_improvement_journey.ipynb`](../../ML_model/notebooks/model_improvement_journey.ipynb)  
>
> This file is **ops/config only** — do not duplicate the training narrative here.

## Production config (promoted artifact)

| Item | Value |
|------|-------|
| Model family | See `run_manifest.json` → `winner` (e.g. `XGBoostDeep`) |
| Feature count | 35 (`backend/data/model_feature_contract.json`) |
| Operating threshold | From policy sweep — see manifest `threshold` |
| Production risk bands | Low ≤ 20% · Medium 21–70% · High > 70% — `services/risk_levels.py` |
| Prediction target | Injury risk **today** (calendar day D), morning inference |

## Live gate (`backend/ml/model_loader.py`)

Model is **Blocked** (no `/predict/daily`) unless manifest passes:

- `Recall@Threshold` ≥ **0.80** (`MIN_RECALL_HARD`)
- `ROC-AUC` ≥ **0.68** (`MIN_AUC_FOR_LIVE`)

Manifest metrics are from **fixed holdout evaluation**. The serialized estimator is **refit on the full training CSV** (`selection_protocol.serving_model_fit` in manifest).

Pointer: `ML_model/artifacts/promoted.json` → `run_manifest.json`, `injury_model.pkl`.

**Serving:** model loads in-process at backend startup. After promotion, restart the server or rebuild the container.

## Training scripts

| Script | Role |
|--------|------|
| `ML_model/data_generator.py` | Synthetic `athlete_injury_data.csv` |
| `ML_model/create_benchmark_set.py` | Fixed `benchmark_holdout.csv` |
| `ML_model/train_model.py` | CV → holdout selection → refit → `artifacts/<run_id>/` |
| `ML_model/validate_metrics.py` | Promotion gates |
| `ML_model/run_pipeline.py` | End-to-end + promote |
