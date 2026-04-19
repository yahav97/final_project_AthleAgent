# Manual ML regression (POST /predict)

After code changes to preprocessing or feature engineering, re-run automated tests, then spot-check with fixed JSON bodies and record `risk_score` / `risk_level` here or in your lab notebook.

## Commands

```bash
cd backend
python -m pytest tests/ -v
python scripts/smoke_uvicorn.py
```

## Training metrics (fill after each `ML_model/train_model.py` run)

Copy the printed block from the training script output, for example:

- Best model name:
- Test F1:
- Test ROC-AUC:

## Sample payloads (paste into `/docs` Try it out or curl)

**1. Rest / low load**

```json
{
  "sleepMinutes": 540,
  "steps": 4000,
  "stressLevel": 20,
  "muscleSoreness": 1,
  "totalCalories": 2400
}
```

**2. Heavy day**

```json
{
  "sleepMinutes": 300,
  "steps": 16000,
  "distanceMeters": 12000,
  "activeCalories": 900,
  "stressLevel": 70,
  "muscleSoreness": 4,
  "totalCalories": 2600
}
```

**3. Poor sleep**

```json
{
  "sleepMinutes": 240,
  "steps": 8000,
  "stressLevel": 50,
  "muscleSoreness": 3
}
```

**4. Minimal body (defaults apply)**

```json
{}
```

**5. Nutrition-heavy day**

```json
{
  "sleepMinutes": 420,
  "steps": 9000,
  "totalCalories": 3200,
  "totalProtein": 150,
  "totalCarbs": 400,
  "mealsLoggedCount": 4,
  "stressLevel": 40,
  "muscleSoreness": 2
}
```

Record observed outputs (date / commit hash):

| Scenario | risk_score | risk_level | Notes |
|----------|------------|------------|-------|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |
