# Android / Firestore integration notes

**Backend change (no app code updated in this repo):** the backend no longer exposes `POST /predict`. If the Android client still calls that path, it must be switched to **`POST /predict/daily`** (minimal JSON below). Until the client is updated, those calls will fail at the HTTP layer.

Preferred production endpoint is **`POST /predict/daily`** with minimal body:

```json
{
  "userId": "uid",
  "date": "yyyy-MM-dd"
}
```

## Field mapping (Firestore → internal request)

| Firestore / Android area | Example field | `InjuryPredictionRequest` field |
|---------------------------|---------------|----------------------------------|
| `users/{uid}/daily_health` | `sleepMinutes` | `sleepMinutes` |
| same | `steps` | `steps` |
| same | `distanceMeters` | `distanceMeters` |
| same | `activeCalories` | `activeCalories` |
| same | `totalCalories` | `totalCalories` |
| same | `heartRateAvg`, `heartRateMax`, `heartRateMin` | same names |
| same | `weightKg`, `bmrCalories` | same names |
| `users/{uid}/daily_checkins` | `energyLevel` | `energyLevel` |
| same | `muscleSoreness` | `muscleSoreness` |
| same | `stressLevel` | `stressLevel` |
| `users/{uid}/daily_nutrition/{date}` | totals / counts | `totalProtein`, `totalCarbs`, `mealsLoggedCount` |

`userId` and `date` are required for `POST /predict/daily` and enable backend persistence of the prediction output.

## Architecture options (decision for the team)

1. **Direct HTTP:** Android calls backend endpoint. Backend can persist prediction output to `users/{uid}/daily_health/{date}` (merge write), including fields like `finalRiskScore`, `riskLevel`, `backendRecommendation`, `predictionMeta`, and `predictionUpdatedAt`.
2. **Cloud intermediary:** A Cloud Function triggered on Firestore writes calls FastAPI with a service account, then writes the prediction — keeps model URL off the device.

## Response contract

JSON fields: `risk_level`, `risk_score` (0-1 probability), `recommendation` (string), `data_quality_score`, `data_quality_status`, `meta`. Not the legacy `risk_percentage` field from `/demo_predict`.

The `recommendation` string is **produced on the backend** (deterministic templates from model probability + ACWR + a history-confidence suffix). After a successful call with `userId` + `date`, the same text is merged into Firestore as **`backendRecommendation`** on `daily_health/{date}`. Any separate **Gemini**-generated coach text in the app (e.g. `aiRecommendation`) is outside this API contract.
