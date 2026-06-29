# ML model



| Resource | Role |

|----------|------|

| [`notebooks/model_improvement_journey.ipynb`](notebooks/model_improvement_journey.ipynb) | **Live demo** — CSV subset → EDA → split → train 5 candidates → policy winner |

| [`artifacts/promoted.json`](artifacts/promoted.json) | Production model pointer (updated by `run_pipeline.py`) |

| `fixtures/athlete_injury_demo.csv` | **In git** — lean demo CSV for the notebook (120 athletes × 150 days) |
| `data_generator.py` | Builds full `athlete_injury_data.csv` (gitignored, ~1000×365 for production) |

| `train_model.py` | Train 5 candidates (`MODEL_CANDIDATE_NAMES`) → tiered policy picks winner → `artifacts/<run_id>/` |

| `validate_metrics.py` | Promotion policy gates |

| `run_pipeline.py` | End-to-end train + validate + promote |



**Production feature contract (no narrative):** [`backend/docs/FEATURES.md`](../backend/docs/FEATURES.md) · [`backend/services/model_features.py`](../backend/services/model_features.py)



**Serving (inference):** via FastAPI backend — local `uvicorn` or Docker ([`docs/DOCKER.md`](../docs/DOCKER.md)). Training scripts run **outside** the container.

## Model candidates (`MODEL_CANDIDATE_NAMES`)

| Model | Role |
|-------|------|
| `LogisticRegression` | Linear baseline — often fails FPR/recall gates |
| `RandomForest` | Bagging ensemble |
| `GradientBoosting` | sklearn boosting |
| `XGBoostCalibratedTuned` | Calibrated XGB — common policy winner |
| `XGBoostDeep` | Deep XGB — high-recall alternative |

Edit the tuple in `train_model.py` to change candidates project-wide.



## Production artifact (current)



| Item | Value |

|------|-------|

| Promoted run | `artifacts/20260629_161704/` |

| Winner | From `pick_best_model()` policy (see `run_manifest.json`) |

| Features | 35 (`backend/data/model_feature_contract.json`) |

| Decision threshold (manifest) | From policy sweep (see `run_manifest.json`) |

| UI risk bands (serving) | Low ≤ 20% · Medium 21–70% · High > 70% |



**Winner metrics (holdout @ 0.18):** Recall **88.7%** · Precision **24.6%** · F1 **38.5%** · ROC-AUC **79.1%**



**Calibration (risk bins):** green 5.6% injury · yellow 16.6% · red **51.5%** injury rate



## Live gate (runtime — `backend/ml/model_loader.py`)



The backend marks the model **Blocked** unless the promoted `run_manifest.json` passes:



- `Recall@Threshold` ≥ **0.80**

- `ROC-AUC` ≥ **0.68**



If blocked → `POST /predict/daily` returns **HTTP 503** (no fallback predictions).



## Per-run artifact layout



```

ML_model/artifacts/<run_id>/

├── injury_model.pkl      # joblib bundle (policy-selected model + preprocessing)

├── run_manifest.json     # metrics, threshold, policy, winner

├── feature_importance.csv

├── model_comparison.csv

└── …                     # calibration / threshold sweep outputs

```



`artifacts/promoted.json` points at the active `injury_model.pkl`. After promotion, **restart** the backend (or rebuild Docker) so `load_model()` picks up the new pointer.



## Retrain from real Firestore data



Export CSV for retraining (backend script, not in this folder):



```bash

python backend/scripts/build_training_dataset_from_firestore.py --help

```



Then point `train_model.py` / `run_pipeline.py` at the exported dataset as needed.



## Quick commands



```bash

# Full synthetic pipeline + promote

python ML_model/run_pipeline.py



# Check serving status (backend must be running)

curl http://localhost:8000/status/ml

```



**Ops reference:** [`backend/docs/MODEL.md`](../backend/docs/MODEL.md)

