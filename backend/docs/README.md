# Backend documentation index

Avoid duplicating content across files. Use this map:

| Document | Purpose |
|----------|---------|
| [**ML notebook appendix**](../../ML_model/notebooks/model_improvement_journey.ipynb) | **Single source** for ML story: data generation, EDA, feature comparison, model scores, charts |
| [`FEATURES.md`](FEATURES.md) | **Production contract only** — Firestore fields, preprocessing, defaults, blocking rules |
| [`MODEL.md`](MODEL.md) | **Production ML config only** — threshold, UI bands, live gate, script paths |
| [`BACKEND.md`](BACKEND.md) | API, architecture, code layout |

**Code of truth for feature names:** `backend/services/model_features.py`
