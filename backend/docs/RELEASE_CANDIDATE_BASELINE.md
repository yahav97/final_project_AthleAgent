# Release Candidate Baseline (Backend)

This document freezes the backend model-selection artifacts used for the current release candidate.

## Locked Source of Truth

- Manifest: `ML_model/run_manifest.json`
- Comparison table: `ML_model/model_comparison.csv`
- Threshold sweep: `ML_model/threshold_sweep.csv`

## Frozen Model Decision

- Winner: `ExtraTrees`
- Operating threshold: `0.36`
- Hard recall gate: `0.85`
- Winner metrics (from manifest):
  - Recall: `0.9696083550913838`
  - Precision: `0.14397146623245716`
  - F1: `0.25071563597083446`
  - FPR: `0.9289188052166597`
  - ROC-AUC: `0.6400128735894797`

## Artifact Integrity (SHA256)

- `ML_model/run_manifest.json`: `7c43196a32878c56b36e1f539fc7ed06f647d80eb61fd756bf3c1b1521380871`
- `ML_model/model_comparison.csv`: `0b96e50e958ff596a2dd1ac729bd233d962b260905a33fb92afa95d0212590ad`
- `ML_model/threshold_sweep.csv`: `14e4a843009b26142a829888beba0cee3cbcb60fcdcebf460785d7bdf00aa5ef`

## Runtime Hardening Guarantees

- Model loading is gated by manifest quality checks (recall and AUC sanity).
- If gate checks fail, backend does not mark model live and serves transparent fallback with reason.
- `POST /predict/daily` response includes prediction provenance metadata:
  - `model_version`
  - `fallback_reason`
  - `confidence_bucket`

## RC Persistence Contract Update

- Application data and prediction outputs are stored in **Firestore** only (no SQL `predictions` table in the current backend).
- Backend Firestore persist no longer writes `predictionSource` to `users/{uid}/daily_health/{date}`.
- Persisted prediction fields are now: `finalRiskScore`, `riskLevel`, `backendRecommendation`, `dataQualityScore`, `dataQualityStatus`, `predictionMeta`, `predictionUpdatedAt`.
- `backendRecommendation` is server-generated ML copy (deterministic rules); it is the same text as the `recommendation` field in the JSON API response for that run.
