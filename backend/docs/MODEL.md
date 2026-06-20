# ML model — production reference

> **Full ML appendix** (synthetic data, feature comparison tables/charts, model selection, metrics evolution):  
> [`ML_model/notebooks/model_improvement_journey.ipynb`](../../ML_model/notebooks/model_improvement_journey.ipynb)  
>
> Do not duplicate that narrative here — this file is **ops/config only**.

## Production config (promoted artifact)

| Item | Value |
|------|-------|
| Model | `XGBoostDeep` |
| Feature count | 36 (`backend/services/model_features.py`) |
| Training threshold | `0.18` — Recall/Precision metrics at promotion (`run_manifest.json`) |
| Production risk bands | Low ≤ 20% · Medium 21–70% · High > 70% — `services/risk_levels.py`, aligned with Android UI |
| Prediction target | Injury risk **today** (calendar day D), morning inference |

## Live gate (`backend/ml/model_loader.py`)

Model is **Blocked** (no `/predict/daily`) unless manifest passes:

- `Recall@Threshold` ≥ **0.85**
- `ROC-AUC` ≥ **0.60**

Pointer: `ML_model/artifacts/promoted.json` → `run_manifest.json`, `injury_model.pkl`.

**Serving:** model loads in-process at backend startup (local `uvicorn` or [`docs/DOCKER.md`](../../docs/DOCKER.md)). After promotion, restart the server or rebuild the container.

## Training pipeline (scripts only)

| Script | Role |
|--------|------|
| `ML_model/data_generator.py` | Build synthetic `athlete_injury_data.csv` |
| `ML_model/train_model.py` | Train candidates, write `artifacts/<run_id>/` |
| `ML_model/validate_metrics.py` | Policy gates |
| `ML_model/run_pipeline.py` | End-to-end + promote |
