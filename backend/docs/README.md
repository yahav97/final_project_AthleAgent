# Backend documentation index

Avoid duplicating content across files. Use this map:

| Document | Purpose |
|----------|---------|
| [**HLD.md**](HLD.md) | **High Level Design** — backend context, architecture, API surface, ML integration |
| [**LLD.md**](LLD.md) | **Low Level Design** — modules, functions, schemas, sequences |
| [**ML notebook appendix**](../../ML_model/notebooks/model_improvement_journey.ipynb) | **Single source** for ML story: data generation, EDA, feature comparison, model scores, charts |
| [`FEATURES.md`](FEATURES.md) | **Production contract only** — Firestore fields, preprocessing, defaults, quality scoring |
| [`RISK_SCORE.md`](RISK_SCORE.md) | **Risk score end-to-end** — ML inference, features, days window, API/Firestore output, thresholds |
| [`MODEL.md`](MODEL.md) | **Production ML config only** — threshold, UI bands, live gate, script paths |
| [`BACKEND.md`](BACKEND.md) | API, architecture, code layout |
| [`../../docs/DOCKER.md`](../../docs/DOCKER.md) | Backend + ML — Docker setup for reviewers |

**Project-wide design docs:** [`docs/HLD_PROJECT.md`](../../docs/HLD_PROJECT.md) · [`docs/LLD_PROJECT.md`](../../docs/LLD_PROJECT.md) · [`docs/DOCKER.md`](../../docs/DOCKER.md)

**Code of truth for feature names:** `backend/services/model_features.py`
