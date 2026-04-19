# Android / Firestore integration notes

The production endpoint is **`POST /predict`** with a JSON body matching [`InjuryPredictionRequest`](../schemas/inference.py) (camelCase keys). The Android app today still calls **`POST /demo_predict`** with a different shape (`AthleteData`); migrating the client is a partner task (requires explicit approval to edit `android_app/`).

## Field mapping (Firestore → API)

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

Optional identifiers: `userId`, `date` (`yyyy-MM-dd`) — useful for logging; the backend does not persist them today.

## Architecture options (decision for the team)

1. **Direct HTTP:** Android builds JSON from Firestore docs and `POST`s to the FastAPI base URL (emulator: host machine IP; not `10.0.2.2` unless the server listens there). Results can be written back to Firestore by the app (e.g. `finalRiskScore` on `daily_health`).
2. **Cloud intermediary:** A Cloud Function triggered on Firestore writes calls FastAPI with a service account, then writes the prediction — keeps model URL off the device.

## Response contract

JSON fields: `risk_level`, `risk_score` (0–1 probability), `recommendation` (string). Not the legacy `risk_percentage` field from `/demo_predict`.
