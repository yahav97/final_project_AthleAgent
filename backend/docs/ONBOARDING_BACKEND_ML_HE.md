# AthleAgent — Backend + ML Onboarding (HE)

מסמך זה מרכז את כל מה שצריך כדי להבין את צד הבקאנד בצורה מקצועית ומהירה.

## 1) תמונת מערכת קצרה

AthleAgent אוספת נתוני יום מספורטאי (Health Connect, check-in, תזונה), ומייצרת ציון סיכון יומי לפציעה.  
הבקאנד אחראי על:
- קבלת טריגר חיזוי מהאפליקציה.
- משיכת נתונים מ-Firestore.
- preprocessing + feature engineering.
- הרצת מודל.
- שמירת תוצאה חזרה ל-Firestore.

## 2) ארכיטקטורת בקאנד

- Framework: `FastAPI`
- Serving logic: `backend/services/prediction_service.py`
- Preprocessing: `backend/services/preprocessing.py`
- Feature list contract: `backend/services/model_features.py`
- History enrichment: `backend/services/history_service.py`
- Model loading + gates: `backend/ml/model_loader.py`
- API routes: `backend/api/routes/predict.py`
- Schemas: `backend/schemas/inference.py`

## 3) מסלולי API שחייבים להכיר

- `POST /predict/daily` (מומלץ לייצור)
  - הקלט המינימלי: `userId`, `date`.
  - הבקאנד מושך לבד profile + daily docs מ-Firestore.
  - מחזיר `InjuryPredictionResponse`.
  - שומר תוצאה חזרה ל-`daily_health/{date}`.
- `POST /predict` (מצב מתקדם/תאימות)
  - קלט מלא מהקליינט.
  - מיועד ל-debug או אינטגרציות מתקדמות.
- `POST /demo_predict`
  - יוריסטיקה legacy/דמו.
  - לא נתיב ייצור.
- `GET /status/ml`
  - סטטוס תפעולי של מודל (`Live`/`Blocked`) ו-gates.

## 4) חוזה פלט ייצור

הפלט המרכזי:
- `risk_score` (0..1)
- `risk_level` (`Low|Medium|High`)
- `recommendation` — נוצר בבקאנד בלבד; תבניות טקסט קבועות לפי הסתברות המודל ו-ACWR, ואז משפט confidence לפי איכות/היסטוריה; נשמר ב-Firestore כ-`backendRecommendation`
- `data_quality_score`
- `data_quality_status`
- `meta` (`model_version`, `fallback_reason`, `confidence_bucket`)

## 5) צינור ML (בקצרה)

תיקיה: `ML_model/`

- `data_generator.py` — יצירת דאטה סינתטי.
- `train_model.py` — אימון מספר מודלים + בחירת winner.
- `validate_metrics.py` — בדיקת gates.
- `run_pipeline.py` — ריצה מלאה + promotion.
- artifacts נשמרים תחת `ML_model/artifacts/<run_id>/`.
- המודל החי מצביע דרך `ML_model/artifacts/promoted.json`.

## 6) מדיניות איכות ובטיחות

- Serving נחסם אם איכות קלט נמוכה מדי (למנוע תוצאה מטעה).
- מודל לא עולה ל-Live אם gate קריטי נכשל.
- fallback לערכי baseline קיים כשחסרים נתונים, אך confidence יורד.
- מודל הייצור צריך לשמור התאמה מלאה בין train features ל-serve features.

## 7) זרימת חיזוי יומית (Production)

1. פרונט שולח `userId + date` ל-`/predict/daily`.
2. הבקאנד מושך snapshot יומי + פרופיל מ-Firestore.
3. preprocessing + הנדסת פיצ'רים + enrichment היסטורי.
4. בדיקת איכות קלט.
5. `predict_proba` על המודל החי.
6. יצירת תגובה מסודרת.
7. persist תוצאת חיזוי ל-Firestore.

## 8) הפעלה מקומית למפתח חדש

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

חובה לוודא:
- credentials תקינים ל-Firebase (`FIREBASE_SERVICE_ACCOUNT_KEY` או `GOOGLE_APPLICATION_CREDENTIALS`).
- גישה לפרויקט Firestore הנכון.

## 9) קבצים לקריאה ראשונה (סדר מומלץ)

1. `backend/api/routes/predict.py`
2. `backend/services/prediction_service.py`
3. `backend/services/preprocessing.py`
4. `backend/services/history_service.py`
5. `backend/schemas/inference.py`
6. `backend/ml/model_loader.py`
7. `backend/services/model_features.py`

## 10) גבולות ברורים בין Frontend ל-Backend

- הפרונט לא מחשב פיצ'רי מודל.
- הפרונט לא מגדיר thresholds.
- הבקאנד הוא מקור האמת לחישוב ושמירת תוצאת חיזוי.
- החוזה הפורמלי נמצא ב-`DATA_CONTRACT_FRONTEND_BACKEND.md`.
