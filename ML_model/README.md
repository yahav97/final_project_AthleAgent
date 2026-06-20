# ML model

| Resource | Role |
|----------|------|
| [`notebooks/model_improvement_journey.ipynb`](notebooks/model_improvement_journey.ipynb) | **Appendix** — data generation, feature comparison, model selection, metrics, charts |
| [`artifacts/promoted.json`](artifacts/promoted.json) | Production model pointer |
| `train_model.py`, `data_generator.py`, `run_pipeline.py` | Training pipeline |

**Production feature contract (no narrative):** `backend/docs/FEATURES.md` · `backend/services/model_features.py`

**Serving (inference):** via FastAPI backend — local `uvicorn` or Docker ([`docs/DOCKER.md`](../docs/DOCKER.md)). Training scripts below run **outside** the container.
