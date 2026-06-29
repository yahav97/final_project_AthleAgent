# AthleAgent — Backend Architecture

## 1. סקירה כללית

AthleAgent אוספת נתוני יום מספורטאי (Health Connect, check-in, תזונה), ומייצרת ציון סיכון יומי לפציעה.

### ארכיטקטורה

```
┌──────────────────────────────────────┐
│           Android App (Kotlin)        │
│  Health Connect · Firebase SDK        │
│  Gemini (תזונה / המלצות — בלקוח בלבד) │
└──────────────────┬───────────────────┘
                   │ HTTP POST /predict/daily
                   │ (trigger: userId + date)
                   ▼
         ┌─────────────────┐
         │  FastAPI Backend │
         └────────┬────────┘
              ┌───┴───┐
              ▼       ▼
        ┌──────────┐ ┌──────────┐
        │ Firestore│ │ ML Model │
        │ read/write│ │ XGBoost  │
        └──────────┘ └──────────┘
```

### טכנולוגיות

- **Frontend**: Android (Kotlin), Health Connect SDK, Firebase Auth (client-side)
- **Backend**: FastAPI (Python), Firestore Admin, ML inference (joblib / XGBoost)
- **ML training**: XGBoost, scikit-learn (מחוץ ל-container — `ML_model/`)
- **Authentication**: Firebase Auth באפליקציה; הבקאנד **לא** מבצע OAuth / Gemini

---

## 2. מבנה הקוד

```
backend/
├── main.py                         # FastAPI entry point (lifespan → load_model)
├── config.py                       # Configuration
├── data/
│   └── model_feature_contract.json # רשימת עמודות + defaults (נטען מהדיסק)
├── api/routes/
│   ├── health.py                   # GET /, GET /health
│   ├── predict.py                  # POST /predict/daily
│   └── observability.py            # client telemetry
├── services/
│   ├── prediction_service.py       # shim — ייבוא תאימות
│   ├── prediction/                 # orchestration, bundle, confidence, firestore mapping
│   ├── history_service.py          # shim — ייבוא תאימות
│   ├── history/                    # Firestore client, repository, rolling features
│   ├── preprocessing/              # quality, validation, scales, request mapping
│   ├── feature_engineering.py      # derived features (ACWR proxies)
│   ├── field_transforms.py         # Firestore field helpers
│   ├── model_features.py           # loader ל-contract JSON (cache בזיכרון)
│   └── risk_levels.py              # Low/Medium/High cutoffs
├── schemas/
│   ├── inference.py                # Pydantic request/response
│   ├── enums.py                    # HistoryConfidence, ModelGateReason, …
│   └── types.py                    # RiskLevel Literal
├── ml/
│   └── model_loader.py             # טעינת מודל + manifest gates
├── middleware/
│   └── request_logging.py
├── utils/
│   ├── logging.py
│   ├── client_event_limiter.py     # rate limit + TTL eviction
│   └── exceptions.py
└── tests/
    ├── unit/
    └── integration/
```

**הערות ארגון:**
- קבצים מעל ~250 שורות פוצלו לחבילות (`preprocessing/`, `history/`, `prediction/`).
- `model_feature_contract.json` נשמר על הדיסק; `model_features.py` טוען פעם אחת (לא רשימות כבדות בקוד).
- `schemas/enums.py` מחליף מחרוזות קבועות (`HistoryConfidence`, `ModelGateReason`, `ModelLiveStatus`).

---

## 3. API Endpoints

### `POST /predict/daily` (ייצור)

**הקלט:**
```json
{
  "userId": "firebase-uid",
  "date": "yyyy-MM-dd"
}
```

**מה קורה בבקאנד:**
1. מושך snapshot יומי + פרופיל מ-Firestore
2. Preprocessing + הנדסת פיצ'רים
3. Enrichment היסטורי (7 ימים)
4. בדיקת איכות קלט
5. `predict_proba` על המודל החי
6. שמירת תוצאה ל-Firestore (merge)

**הפלט (API — לצורכי אימות/דיבוג, לא לתצוגה באפליקציה):**
```json
{
  "risk_score": 0.25,
  "risk_level": "Medium",
  "prediction_confidence": 82.5
}
```

> **`risk_score` ב-API הוא הסתברות 0–1** (פלט ML). **האפליקציה לא קוראת את גוף התשובה** — רק בודקת `response.isSuccessful`.  
> **מקור האמת לתצוגה:** Firestore → `finalRiskScore` (0–100). ראו [§6.1](#61-מקור-האמת-לתצוגה-firestore-לא-תגובת-post).

**שדות שנשמרים ב-Firestore** (`daily_health/{date}` merge):
- `finalRiskScore` (0–100)
- `riskLevel`
- `predictionConfidence`
- `predictionUpdatedAt`

### `POST /test_predict` (mock — לא ייצור)

מחזיר תשובה קבועה ל-smoke tests של UI/API (`risk_percentage: 72.5`, `risk_level: High`). דורש `ENABLE_TEST_PREDICT_ENDPOINT=true`; אחרת מחזיר `404`.

### `GET /status/ml` (סטטוס תפעולי)

---

## 4. Firestore — מבנה נתונים

### אוספים

| נתיב | תיאור |
|------|--------|
| `users/{uid}` | פרופיל: uid, fullName, email, role, teamId |
| `users/{uid}/daily_health/{date}` | בריאות יומית + תוצאות חיזוי |
| `users/{uid}/daily_checkins/{date}` | דיווח עצמי (סטרס, כאב, אנרגיה) |
| `users/{uid}/daily_nutrition/{date}` | אגרגציית תזונה יומית |
| `users/{uid}/daily_nutrition/{date}/meals/{id}` | פירוט ארוחות (לא נטען בבקאנד) |
| `teams/{teamId}` | קבוצה: `teamCode`, `TeamName`, `coachId`, `athletes[]` |
| `teams/{teamId}/requests/{uid}` | בקשות הצטרפות |

### שדות `daily_health/{date}`

**מהאפליקציה (סנכרון — יעד לפרונט):**
- `{D}`: `sleepMinutes` (בוקר), עומס פיזי **חלקי** במהלך היום
- `{D-1}`: עומס פיזי **יום מלא** (נדרס בבוקר D עם אגרגציה 00:00–23:59)

שדות פיזיים: `steps`, `distanceMeters`, `activeCalories`, `totalCalories`, `bmrCalories`, `heartRateAvg`, `heartRateMax`, `heartRateMin`, `weightKg`, `lastSync`

> פירוט מלא: [FEATURES.md — משימות Android](FEATURES.md#משימות-android--סנכרון-שעון-לשותף-פרונט)

**מהבקאנד (אחרי חיזוי):**
`finalRiskScore`, `riskLevel`, `predictionConfidence`, `predictionUpdatedAt`

### Retention Policy

- **אין מחיקה אוטומטית** של ימים ישנים
- 7 ימים = חלון חישובי בלבד (lookback למודל)
- יעד מומלץ: שמירת 90-180 יום minimum

---

## 5. זרימת חיזוי (Production Flow)

```
Android → POST /predict/daily (userId + date)
    │
    ▼
Backend loads from Firestore:
    ├── users/{uid} (profile)
    ├── daily_health/{date}          ← sleep (last night)
    ├── daily_health/{date-1}        ← physical load (yesterday)
    ├── daily_checkins/{date}        ← survey (today)
    └── daily_nutrition/{date-1}     ← nutrition (yesterday)
    │
    ▼
Preprocessing:
    • המרות יחידות וסקאלה
    • חישוב BMI, workout intensity
    • Fallbacks לנתונים חסרים
    │
    ▼
History Enrichment (7 days):
    • acute_load_7d, acwr_ratio
    • acwr_ratio, sleep_debt_3d, hrv_drop
    │
    ▼
Data Quality Check:
    • quality_score מוריד prediction_confidence (לא חוסם חיזוי)
    • hard_missing מקסימום score 0.25 — נרשם בלוג בלבד
    │
    ▼
Model Inference (promoted bundle):
    • 35 features → predict_proba
    • classify_risk_level(proba) — Low ≤ 20%, Medium 21–70%, High > 70%
    │
    ▼
Response + Persist to Firestore (merge write)
```

---

## 6. Data Contract (Frontend ↔ Backend)

### 6.1 מקור האמת לתצוגה: Firestore, לא תגובת POST

זרימת החיזוי בפרודקשן **תקינה** — אין חוסר התאמה בפועל:

| שלב | מה קורה |
|-----|---------|
| 1 | אנדרואיד שולח `POST /predict/daily` עם `{ userId, date }` |
| 2 | הבקאנד מחשב `risk_score` (0–1) ושומר ל-Firestore: `finalRiskScore = risk_score × 100` |
| 3 | האפליקציה **לא קוראת** את `risk_score` מתגובת ה-HTTP — רק `isSuccessful` |
| 4 | דשבורד ספורטאי/מאמן קורא **`finalRiskScore`** מ-`daily_health/{date}` ומציג 0–100% |

**לכן:** ההבדל בין `risk_score` (0–1) ב-API לבין `finalRiskScore` (0–100) ב-Firestore הוא **המרה מכוונת**, לא באג.  
`ApiService.PredictionResponse` ב-Retrofit מוגדר לצורך טיפוס/לוג — לא לתצוגת UI.

### 6.2 נושאים אחרים לתיאום עם פרונט (אופציונלי)

| נושא | Android | Backend | דחיפות |
|------|---------|---------|--------|
| **DTO ישן** | `PredictionModels.kt` (לא בשימוש) | `InjuryPredictionResponse` | ניקוי תיעוד בלבד |
| **תאריך עומס פיזי** | כותב שינה ל-`{D}`, עומס ל-`{D-1}` (`WearableSyncActivity`) | קורא עומס מ-`{D-1}` בלבד | מיושם |
| **Gate לפני trigger** | `DailyCheckIn`: `sleepMinutes` ב-`{D}`; `WearableSync`: `energyLevel` ב-`daily_checkins/{D}` | אין חסימת HTTP על עומס חסר — רק `prediction_confidence` | **פער:** אין בדיקת `steps>0` ב-`{D-1}` בפרונט |
| **Endpoints** | רק `POST /predict/daily` | גם `/health`, `/status/ml` — לא מחוברים | אין השפעה |

### Trigger (מהאפליקציה)

הפרונט שולח רק `userId` + `date` ל-`POST /predict/daily`.
הבקאנד מושך הכל בעצמו מ-Firestore.

### Required Minimum Daily Fields

השדות שחייבים להיות ב-Firestore לחיזוי יציב:
`sleepMinutes` ב-`daily_health/{date}`, `steps` ושאר העומס ב-`daily_health/{date-1}`,
`stressLevel` / `muscleSoreness` ב-`daily_checkins/{date}`, תזונה ב-`daily_nutrition/{date-1}`

### Recommendation Text

- המלצת טקסט למשתמש נוצרת **באפליקציה** דרך Gemini → נשמרת כ-`aiRecommendation` ב-Firestore
- הבקאנד **לא** מחזיר שדה `recommendation` ולא כותב `backendRecommendation`

### הבחנה חשובה: קלוריות

| שדה | מקור | משמעות |
|-----|------|--------|
| `daily_health.totalCalories` | Health Connect | **שריפה** (expenditure) |
| `daily_nutrition.totalCalories` | אפליקציה | **צריכה** (intake) |

לא לבלבל ביניהם!

---

## 7. גבולות אחריות

| נושא | Frontend | Backend |
|------|----------|---------|
| חישוב פיצ'רי מודל | ✗ | ✓ |
| הגדרת thresholds | ✗ | ✓ |
| שמירת תוצאת חיזוי | ✗ | ✓ |
| סנכרון Health Connect | ✓ | ✗ |
| כתיבת נתונים יומיים ל-Firestore | ✓ | ✗ (רק תוצאת חיזוי) |
| הצגת confidence למשתמש | ✓ | מספק את הערך |
| קריאה ל-Gemini (תזונה) | ✓ | ✗ |

---

## 8. הפעלה

### Docker (מומלץ לבוחנים)

מתוך שורש הריפו — פירוט מלא: [`docs/DOCKER.md`](../../docs/DOCKER.md)

```bash
# backend/firebase-key.json חייב להיות קיים לפני ההרצה הראשונה
docker compose up --build
```

אימות: `GET http://localhost:8000/status/ml` → `"status": "Live"`.

### Python מקומי (פיתוח)

```bash
pip install -r backend/requirements.txt
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**דרישות (שני המסלולים):**
- Firebase credentials: `FIREBASE_SERVICE_ACCOUNT_KEY` או `GOOGLE_APPLICATION_CREDENTIALS`
- גישה לפרויקט Firestore (`athleagent`)

### Environment Variables

כל ההגדרות הניתנות לשינוי מרוכזות ב-`config.py` (pydantic-settings). תבנית מלאה: `backend/.env.example`.

```env
# העתק ל-backend/.env
FIREBASE_SERVICE_ACCOUNT_KEY=backend/firebase-key.json
LOG_LEVEL=INFO

# דגלי פיצ'ר
ENABLE_TEST_PREDICT_ENDPOINT=false

# שערי ML (staging יכול להרחיב)
ML_MIN_RECALL_HARD=0.80
ML_MIN_AUC_FOR_LIVE=0.68

# ספי סיכון (חייבים להתאים לאנדרואיד)
RISK_HIGH_CUTOFF=0.70
RISK_MEDIUM_CUTOFF=0.20
```

קבוצות נוספות: חלון היסטוריה, משקלי confidence, imputation תזונה, rate limits — ראה `config.py`.

---

## 9. Tests

הטסטים ב-`backend/tests/`:
- Preprocessing shape/type/no-NaN
- Profile override tests
- History rolling/confidence behavior
- Prediction column alignment

---

## 10. קבצים חשובים לקריאה

| קובץ | תפקיד |
|------|--------|
| `config.py` | כל ההגדרות והקבועים הניתנים ל-override |
| `api/routes/predict.py` | נתיבי API |
| `services/prediction/` | לוגיקת חיזוי (service, bundle, confidence) |
| `services/preprocessing/` | הנדסת פיצ'רים + איכות נתונים |
| `services/history/` | היסטוריה + Firestore |
| `data/model_feature_contract.json` | 35 עמודות + defaults |
| `schemas/inference.py` | Pydantic models |
| `schemas/enums.py` | Enum-ים לסטטוסים ו-confidence |
| `ml/model_loader.py` | טעינת מודל + gates |
