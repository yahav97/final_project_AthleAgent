# Backend documentation index

Avoid duplicating content across files. Use this map:

| Document | Purpose |
|----------|---------|
| [`../README.md`](../README.md) | **Start here** — run locally/Docker, config, API sketch, tests |
| [`HLD.md`](HLD.md) | Backend architecture & prediction flow |
| [`FEATURES.md`](FEATURES.md) | Production contract — Firestore fields, preprocessing, defaults, quality |
| [`RISK_SCORE.md`](RISK_SCORE.md) | Risk score end-to-end — inference, features, API/Firestore output |
| [`MODEL.md`](MODEL.md) | Production ML config — threshold, UI bands, live gate |
| [`../../docs/DOCKER.md`](../../docs/DOCKER.md) | Docker setup for reviewers |
| [**ML notebook appendix**](../../ML_model/notebooks/model_improvement_journey.ipynb) | ML story: data, EDA, scores, charts |

**Project-wide design:** [`docs/HLD_PROJECT.md`](../../docs/HLD_PROJECT.md) · [`docs/LLD_PROJECT.md`](../../docs/LLD_PROJECT.md) · [`docs/NFR.md`](../../docs/NFR.md)

**Code of truth for feature names:** `backend/services/model_features.py` + `backend/data/model_feature_contract.json`
