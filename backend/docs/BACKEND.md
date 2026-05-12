# AthleAgent — Backend Architecture

## 1. סקירה כללית

AthleAgent אוספת נתוני יום מספורטאי (Health Connect, check-in, תזונה), ומייצרת ציון סיכון יומי לפציעה.

### ארכיטקטורה

```
┌─────────────────┐
│  Android App    │  (Kotlin)
└────────┬────────┘
         │ HTTP/REST + Firebase Auth
         ▼
┌─────────────────┐
│  FastAPI Backend│  (Python)
└────────┬────────┘
    ┌────┴────┬──────────────┬─────────────┐
    ▼         ▼              ▼             ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│Firestore │ │Gemini AI │ │Health    │ │ML Model  │
│(App data)│ │(אופציונלי│ │Connect   │ │(XGBoost/ │
│          │ │ בלקוח)   │ │(Android) │ │joblib)   │
└──────────┘ └──────────┘ └──────────┘ └──────────┘
```

### טכנולוגיות

- **Frontend**: Android (Kotlin), Health Connect SDK
- **Backend**: FastAPI (Python), Firestore, ML inference
- **ML**: XGBoost, scikit-learn, joblib
- **External APIs**: Google Gemini AI (ניתוח תזונה באפליקציה), Firebase
- **Authentication**: Firebase Auth (בצד האפליקציה)

---

## 2. מבנה הקוד

```
backend/
├── main.py                         # FastAPI entry point
├── config.py                       # Configuration
├── api/routes/
│   └── predict.py                  # POST /predict/daily, POST /demo_predict
├── services/
│   ├── prediction_service.py       # לוגיקת חיזוי ראשית
│   ├── preprocessing.py            # הנדסת פיצ'רים + איכות נתונים
│   ├── history_service.py          # היסטוריה מ-Firestore + rolling features
│   └── model_features.py          # רשימת פיצ'רים + defaults
├── schemas/
│   └── inference.py                # Pydantic schemas (request/response)
├── ml/
│   └── model_loader.py            # טעינת מודל + gates
└── tests/                          # pytest
```

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

**הפלט:**
```json
{
  "risk_score": 0.25,
  "risk_level": "Medium",
  "recommendation": "Consider reducing training load...",
  "data_quality_score": 0.85,
  "data_quality_status": "good"
}
```

**שדות שנשמרים ב-Firestore** (`daily_health/{date}` merge):
- `finalRiskScore` (0-100)
- `riskLevel`
- `backendRecommendation`
- `dataQualityScore`
- `dataQualityStatus`
- `predictionUpdatedAt`

### `POST /demo_predict` (legacy/דמו — לא ייצור)

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
| `teams/{teamId}` | קבוצה: TeamCode, TeamName, coachId, athletes[] |
| `teams/{teamId}/requests/{uid}` | בקשות הצטרפות |

### שדות `daily_health/{date}`

**מהאפליקציה (סנכרון):**
`sleepMinutes`, `steps`, `distanceMeters`, `activeCalories`, `totalCalories`, `bmrCalories`, `heartRateAvg`, `heartRateMax`, `heartRateMin`, `weightKg`, `lastSync`

**מהבקאנד (אחרי חיזוי):**
`finalRiskScore`, `riskLevel`, `backendRecommendation`, `dataQualityScore`, `dataQualityStatus`, `predictionUpdatedAt`

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
    ├── daily_health/{date}
    ├── daily_checkins/{date}
    └── daily_nutrition/{date}
    │
    ▼
Preprocessing:
    • המרות יחידות וסקאלה
    • חישוב BMI, workout intensity
    • Fallbacks לנתונים חסרים
    │
    ▼
History Enrichment (7 days):
    • acute_load_7d, chronic_load_21d
    • acwr_ratio, sleep_debt_3d, hrv_drop
    │
    ▼
Data Quality Check:
    • quality_score < 0.35? → BLOCK
    • hard_missing? → BLOCK (unless history softens)
    │
    ▼
Model Inference (XGBoostDeep):
    • 34 features → predict_proba
    • threshold = 0.18 → risk_level
    │
    ▼
Response + Persist to Firestore (merge write)
```

---

## 6. Data Contract (Frontend ↔ Backend)

### Trigger (מהאפליקציה)

הפרונט שולח רק `userId` + `date` ל-`POST /predict/daily`.
הבקאנד מושך הכל בעצמו מ-Firestore.

### Required Minimum Daily Fields

השדות שחייבים להיות ב-Firestore לחיזוי יציב:
`sleepMinutes`, `steps`, `distanceMeters`, `activeCalories`, `totalCalories`, `heartRateAvg`, `weightKg`, `bmrCalories`, `stressLevel`, `muscleSoreness`

### Recommendation Text

- שדה `recommendation` ב-API = `backendRecommendation` ב-Firestore
- נוצר **בבקאנד בלבד** — תבניות טקסט קבועות לפי הסתברות + ACWR + confidence
- דטרמיניסטי — אפשר לשחזר מאותם קלטים
- **נפרד** מהמלצת Gemini באפליקציה (`aiRecommendation`)

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

## 8. הפעלה מקומית

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**דרישות:**
- Firebase credentials: `FIREBASE_SERVICE_ACCOUNT_KEY` או `GOOGLE_APPLICATION_CREDENTIALS`
- גישה לפרויקט Firestore (`athleagent`)

### Environment Variables

```env
FIREBASE_SERVICE_ACCOUNT_KEY=/path/to/service-account.json
GOOGLE_CLIENT_ID=your-google-client-id       # אופציונלי
GEMINI_API_KEY=your-gemini-api-key           # אופציונלי
```

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
| `api/routes/predict.py` | נתיבי API |
| `services/prediction_service.py` | לוגיקת חיזוי |
| `services/preprocessing.py` | הנדסת פיצ'רים |
| `services/history_service.py` | היסטוריה + Firestore |
| `services/model_features.py` | רשימת עמודות + defaults |
| `schemas/inference.py` | Pydantic models |
| `ml/model_loader.py` | טעינת מודל + gates |
