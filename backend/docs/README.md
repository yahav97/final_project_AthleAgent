# Backend documentation index

Avoid duplicating content across files. Use this map:

| Document | Purpose |
|----------|---------|
| [`FEATURES.md`](FEATURES.md) | **Production contract only** — Firestore fields, preprocessing, defaults, quality scoring |
| [`RISK_SCORE.md`](RISK_SCORE.md) | **Risk score end-to-end** — ML inference, features, days window, API/Firestore output, thresholds |
| [`MODEL.md`](MODEL.md) | **Production ML config only** — threshold, UI bands, live gate, script paths |
| [`BACKEND.md`](BACKEND.md) | API, architecture, code layout |
| [`../../docs/DOCKER.md`](../../docs/DOCKER.md) | Backend + ML — Docker setup for reviewers |
| [**ML notebook appendix**](../../ML_model/notebooks/model_improvement_journey.ipynb) | ML story: data generation, EDA, feature comparison, model scores, charts |

**Project-wide design docs (HLD / LLD):** [`docs/HLD_PROJECT.md`](../../docs/HLD_PROJECT.md) · [`docs/LLD_PROJECT.md`](../../docs/LLD_PROJECT.md) · [`docs/NFR.md`](../../docs/NFR.md)

**Code of truth for feature names:** `backend/services/model_features.py` + `backend/data/model_feature_contract.json` (`integer_feature_columns`)
