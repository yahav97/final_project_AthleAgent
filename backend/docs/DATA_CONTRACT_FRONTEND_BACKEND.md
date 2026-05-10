# Frontend-Backend Data Contract (Injury Risk)

This document defines the production daily contracts between Android/Firestore and backend prediction endpoints.
Goal: prevent train/serve drift and prevent missing-field surprises before model work.

**Feature roadmap (HE, Firestore inventory vs ML):** see [`FEATURE_PLAN_FIRESTORE_HE.md`](FEATURE_PLAN_FIRESTORE_HE.md).

## Scope

- Production backend endpoint: `POST /predict/daily` (minimal trigger; backend loads Firestore directly)
- Internal assembled request type (server-side only): `backend/schemas/inference.py` (`InjuryPredictionRequest`)
- Current Android storage:
  - `users/{uid}/daily_health/{yyyy-MM-dd}`
  - `users/{uid}/daily_checkins/{yyyy-MM-dd}`
  - `users/{uid}/daily_nutrition/{yyyy-MM-dd}`
- Weekly history UI: last 7 `finalRiskScore` points from `daily_health` (display only).

## Recommended Production Trigger (client -> backend)

Preferred minimal request:

```json
{
  "userId": "uid",
  "date": "yyyy-MM-dd"
}
```

Behavior:
- Backend loads same-day docs from Firestore (`daily_health`, `daily_checkins`, `daily_nutrition`) plus profile from `users/{uid}`.
- Backend computes features + historical enrichment internally and runs inference.
- Backend persists prediction output back to `users/{uid}/daily_health/{date}` (merge write) and also returns the same response to the client.
- This keeps Firestore as a single source of truth and avoids split logic between client and server.

Persisted fields in `daily_health` after successful prediction (merge write):
- `finalRiskScore` (0-100)
- `riskLevel`
- `backendRecommendation`
- `dataQualityScore`
- `dataQualityStatus`
- `predictionUpdatedAt`

### ML recommendation text (`recommendation` / `backendRecommendation`)

- The HTTP field `recommendation` and the Firestore field `backendRecommendation` are the **same string** for a given successful prediction.
- **Source of truth:** computed on the server in `backend/services/prediction_service.py` (not assembled in the mobile UI).
- **Rules (deterministic):** a small fixed set of English templates chosen from model **probability** (`risk_score` / `predict_proba`) and **ACWR** (`acwr_ratio`), then a trailing **confidence** sentence based on history coverage (high / medium / low). Thresholds for recommendation wording are **not** identical to `risk_level` cutoffs (those come from the saved model bundle thresholds).
- **Optional client copy:** the Android app may still call **Gemini** and store a separate coach-facing string (e.g. `aiRecommendation`). That path is **independent** of this contract and must not be confused with `backendRecommendation`.

## Internal assembled payload (server-side)

The backend builds an `InjuryPredictionRequest` from Firestore (`profile`, `daily_health`, `daily_checkins`, `daily_nutrition` for the target date). Clients do **not** send this JSON over HTTP; it documents the merged field set used inside `prediction_service.py`.

## Required Minimum Daily Fields (for stable model signal)

These fields must be present daily (or explicitly set to `0` when truly absent):

- `sleepMinutes`
- `steps`
- `distanceMeters`
- `activeCalories`
- `totalCalories`
- `heartRateAvg`
- `weightKg`
- `bmrCalories`
- `stressLevel`
- `muscleSoreness`

If missing repeatedly, backend falls back to defaults and signal quality drops.

## Exact Mapping: Firestore -> API -> Model

| Firestore source | Field | Assembled key (`InjuryPredictionRequest`) | Model usage |
|---|---|---|---|
| `users/{uid}` (profile) | `age` | `age` | `age` |
| `users/{uid}` (profile) | `historyInjuryCount` | `historyInjuryCount` | `history_injury_count` |
| `daily_health` | `sleepMinutes` | `sleepMinutes` | `sleep_hours` |
| `daily_health` | `steps` | `steps` | `daily_distance_km` fallback, `avg_cadence` |
| `daily_health` | `distanceMeters` | `distanceMeters` | `daily_distance_km` primary |
| `daily_health` | `activeCalories` | `activeCalories` | `workout_intensity_minutes`, load proxies |
| `daily_health` | `totalCalories` | `totalCalories` | **`total_calories_burned`** (energy expenditure from Health Connect). Does **not** set intake `daily_calories`. |
| `daily_health` | `heartRateAvg` | `heartRateAvg` | `resting_hr`, `hrv_score` proxy |
| `daily_health` | `heartRateMax` | `heartRateMax` | accepted, not used today |
| `daily_health` | `heartRateMin` | `heartRateMin` | accepted, not used today |
| `daily_health` | `weightKg` | `weightKg` | `bmi` (fixed height assumption) |
| `daily_health` | `bmrCalories` | `bmrCalories` | burned proxy |
| `daily_checkins` | `energyLevel` | `energyLevel` | accepted, not used today |
| `daily_checkins` | `muscleSoreness` | `muscleSoreness` | `muscle_soreness` (scaled) |
| `daily_checkins` | `stressLevel` | `stressLevel` | `stress_level` (scaled) |
| `daily_nutrition` | `totalCalories` | *(not mapped)* | Intake sum stored by Android on nutrition doc; **not** wired into `InjuryPredictionRequest` yet — avoid confusing with `daily_health.totalCalories` (burn). Planned rename: `nutritionTotalCalories` — see [`FEATURE_PLAN_FIRESTORE_HE.md`](FEATURE_PLAN_FIRESTORE_HE.md). |
| `daily_nutrition` | `totalProtein` | `totalProtein` | Feeds **intake estimate** → `daily_calories` via macros in `preprocessing.py` |
| `daily_nutrition` | `totalCarbs` | `totalCarbs` | Same |
| `daily_nutrition` | `mealsLoggedCount` | `mealsLoggedCount` | Same; also scales default intake when macros empty |

## Model Features in Serving (current)

Backend model features are fixed to:

- `age`, `bmi`, `history_injury_count`, `vo2_max` *(column still present in the bundle; filled with a **fixed serving constant**, not from Firestore or clients)*
- `daily_distance_km`, `workout_intensity_minutes`, `avg_cadence`
- `sleep_hours`, `hrv_score`, `resting_hr`
- `daily_calories`, `total_calories_burned`
- `stress_level`, `muscle_soreness`
- `acute_load_7d`, `chronic_load_21d`, `acwr_ratio`
- `calorie_balance`, `sleep_debt_3d`, `hrv_drop`

Important:
- `age`, `historyInjuryCount`: loaded from `users/{uid}` when present; otherwise defaults in `preprocessing`. **`vo2_max` is not a product field** — the trained estimator still expects the column; inference always sets it to `DEFAULT_FEATURE_VALUES["vo2_max"]` in code (no Firestore or client input).
- `acute/chronic/acwr/sleep_debt/hrv_drop`: when enough historical rows exist from Firestore (`daily_health` + `daily_checkins`), rolling values are computed; otherwise the backend uses single-day proxies (`feature_engineering` / defaults).

## Weekly History Clarification

- Athlete/Coach dashboards show last 7 days of `finalRiskScore` saved in `daily_health`.
- This weekly chart is display/history only.
- Serving reads up to 7 historical days from Firestore when resolving rolling features for a given `userId` and `date`.
- If Firestore is unavailable or insufficient history exists, backend falls back to single-day proxy derived features.

## Implementation Status

Completed:

1. Backend exposes `POST /predict/daily` as the only HTTP inference entrypoint.
2. Backend loads profile + daily docs directly from Firestore for that date.
3. Full daily signals are merged into `InjuryPredictionRequest` inside the service layer (not posted by the client).

## Gaps To Close Before Next Model Iteration

1. Migrate Android prediction call to production `POST /predict/daily` minimal trigger (not legacy `demo_predict`).
2. Ensure Android never targets removed **`POST /predict`** (backend-only endpoint removed); use **`POST /predict/daily`** only.
3. Ensure Android always sends `userId` + `date` and handles backend response persistence/UI.
4. Nutrition feature policy decided (see section below): keep raw nutrition fields out of v1 model columns, use them only to derive `daily_calories`.
5. Decide whether `heartRateMax/Min` and `energyLevel` should be converted to model features.
6. Add train-serve compatibility check: training columns must match serving columns exactly (order and names).
7. Add ingestion health checks: flag days with missing required minimum fields.
8. Configure backend runtime credentials for Firestore (`GOOGLE_APPLICATION_CREDENTIALS`) in each environment.

## Decision: "Lost Features" Policy (v1)

To avoid train-serve drift and unnecessary model complexity in v1:

- Keep collecting `totalProtein`, `totalCarbs`, `mealsLoggedCount`, `energyLevel`.
- Do **not** add them as direct model columns in v1.
- Use nutrition only through derived intake logic in preprocessing (`daily_calories` estimate).
- Treat these fields as **reserved for v2 feature expansion** after baseline model stabilizes.

Rationale:
- Reduces missing-data sensitivity and retraining overhead.
- Keeps strict column contract stable while history-based logic is being finalized.
- Prevents "half integrated" features that exist in payload but are weakly represented in training.

Promotion rule for v2:
- A field is promoted to a model feature only if it is available on at least 90% of days in pilot data and improves Recall/F1 in offline evaluation.

## Release Gate (must pass before model tuning)

- Android persists canonical daily field keys to **Firestore** on schedule; the inference HTTP call is only `userId` + `date` to `POST /predict/daily` (no full JSON body to the backend).
- Required minimum daily fields populated for at least 14 consecutive days in test users.
- No unknown train-only feature in training dataset.
- No serve-only feature missing from training dataset.
