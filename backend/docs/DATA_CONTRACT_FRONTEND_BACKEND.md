# Frontend-Backend Data Contract (Injury Risk)

This document defines the exact daily data contract between Android/Firestore and backend `POST /predict`.
Goal: prevent train/serve drift and prevent missing-field surprises before model work.

## Scope

- Backend endpoint: `POST /predict`
- Request schema: `backend/schemas/inference.py` (`InjuryPredictionRequest`)
- Current Android storage:
  - `users/{uid}/daily_health/{yyyy-MM-dd}`
  - `users/{uid}/daily_checkins/{yyyy-MM-dd}`
  - `users/{uid}/daily_nutrition/{yyyy-MM-dd}`
- Weekly history UI: last 7 `finalRiskScore` points from `daily_health` (display only).

## Canonical Daily Payload (client -> backend)

These keys should be sent every day when available:

```json
{
  "userId": "uid",
  "date": "yyyy-MM-dd",
  "age": 0,
  "vo2Max": 0,
  "historyInjuryCount": 0,
  "sleepMinutes": 0,
  "steps": 0,
  "distanceMeters": 0,
  "activeCalories": 0,
  "totalCalories": 0,
  "heartRateAvg": 0,
  "heartRateMax": 0,
  "heartRateMin": 0,
  "weightKg": 0.0,
  "bmrCalories": 0,
  "energyLevel": 0,
  "muscleSoreness": 0,
  "stressLevel": 0,
  "totalProtein": 0,
  "totalCarbs": 0,
  "mealsLoggedCount": 0
}
```

Notes:
- Backend currently accepts all fields as optional and imputes defaults.
- For model quality, daily sender should target near-complete payload (at least required minimum below).

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

| Firestore source | Field | API key (`/predict`) | Model usage |
|---|---|---|---|
| `users/{uid}` (profile) | `age` | `age` | `age` |
| `users/{uid}` (profile) | `vo2Max` | `vo2Max` | `vo2_max` |
| `users/{uid}` (profile) | `historyInjuryCount` | `historyInjuryCount` | `history_injury_count` |
| `daily_health` | `sleepMinutes` | `sleepMinutes` | `sleep_hours` |
| `daily_health` | `steps` | `steps` | `daily_distance_km` fallback, `avg_cadence` |
| `daily_health` | `distanceMeters` | `distanceMeters` | `daily_distance_km` primary |
| `daily_health` | `activeCalories` | `activeCalories` | `workout_intensity_minutes`, load proxies |
| `daily_health` | `totalCalories` | `totalCalories` | `daily_calories`, burned proxy |
| `daily_health` | `heartRateAvg` | `heartRateAvg` | `resting_hr`, `hrv_score` proxy |
| `daily_health` | `heartRateMax` | `heartRateMax` | accepted, not used today |
| `daily_health` | `heartRateMin` | `heartRateMin` | accepted, not used today |
| `daily_health` | `weightKg` | `weightKg` | `bmi` (fixed height assumption) |
| `daily_health` | `bmrCalories` | `bmrCalories` | burned proxy |
| `daily_checkins` | `energyLevel` | `energyLevel` | accepted, not used today |
| `daily_checkins` | `muscleSoreness` | `muscleSoreness` | `muscle_soreness` (scaled) |
| `daily_checkins` | `stressLevel` | `stressLevel` | `stress_level` (scaled) |
| `daily_nutrition` | `totalProtein` | `totalProtein` | accepted, not used today |
| `daily_nutrition` | `totalCarbs` | `totalCarbs` | accepted, not used today |
| `daily_nutrition` | `mealsLoggedCount` | `mealsLoggedCount` | accepted, not used today |

## Model Features in Serving (current)

Backend model features are fixed to:

- `age`, `bmi`, `history_injury_count`, `vo2_max`
- `daily_distance_km`, `workout_intensity_minutes`, `avg_cadence`
- `sleep_hours`, `hrv_score`, `resting_hr`
- `daily_calories`, `total_calories_burned`
- `stress_level`, `muscle_soreness`
- `acute_load_7d`, `chronic_load_21d`, `acwr_ratio`
- `calorie_balance`, `sleep_debt_3d`, `hrv_drop`

Important:
- `age`, `historyInjuryCount`, `vo2Max` are now supported in `/predict`; if omitted, serving falls back to defaults.
- `acute/chronic/acwr/sleep_debt/hrv_drop` are single-day proxies in serving, not true rolling history from Firestore.

## Weekly History Clarification

- Athlete/Coach dashboards show last 7 days of `finalRiskScore` saved in `daily_health`.
- This weekly chart is display/history only.
- Current `/predict` reads up to 7 historical days from Firestore when both `userId` and `date` are provided.
- If Firestore is unavailable or insufficient history exists, backend falls back to single-day proxy derived features.

## Gaps To Close Before Next Model Iteration

1. Migrate Android prediction call to production `POST /predict` contract (not legacy `demo_predict` shape).
2. Ensure Android always includes profile fields `age`, `vo2Max`, `historyInjuryCount` in request payload.
3. Nutrition feature policy decided (see section below): keep raw nutrition fields out of v1 model columns, use them only to derive `daily_calories`.
4. Decide whether `heartRateMax/Min` and `energyLevel` should be converted to model features.
5. Add train-serve compatibility check: training columns must match serving columns exactly (order and names).
6. Add ingestion health checks: flag days with missing required minimum fields.
7. Configure backend runtime credentials for Firestore (`GOOGLE_APPLICATION_CREDENTIALS`) in each environment.

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

- Android sends canonical daily payload keys to backend.
- Required minimum daily fields populated for at least 14 consecutive days in test users.
- No unknown train-only feature in training dataset.
- No serve-only feature missing from training dataset.
