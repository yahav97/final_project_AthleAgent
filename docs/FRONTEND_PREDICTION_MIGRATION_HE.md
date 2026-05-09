# מסמך מעבר פרונט: חיזוי סיכון יומי (Production)

מטרה: ליישר את זרימת הפרונט כך שבכל בוקר, אחרי שמירת נתוני היום, תופעל בקשת חיזוי ל־`POST /predict/daily` (ולא `demo_predict`) עם טריגר מינימלי בלבד: `userId + date`.

---

## תמונת מצב נוכחית בקוד (מה קיים עכשיו)

- ב־Android עדיין קיימת קריאה ל־`/demo_predict` עם payload מורחב (`AthleteData`).
- מודל התגובה באנדרואיד (`PredictionResponse`) עדיין מותאם ל־legacy (`risk_percentage`, `message`).
- ב־Backend נתיב הייצור הפעיל הוא:
  - `POST /predict/daily` עם `DailyPredictionTriggerRequest`:
    - `userId: string`
    - `date: string` (`yyyy-MM-dd`)
  - תגובה מסוג `InjuryPredictionResponse`:
    - `risk_score` (0..1)
    - `risk_level`
    - `recommendation`
    - `data_quality_score`
    - `data_quality_status`
    - `meta` (`model_version`, `fallback_reason`, `confidence_bucket`)
  - הבקאנד שומר אוטומטית את תוצאת החיזוי למסמך היום ב־Firestore (`daily_health/{date}`) וגם מחזיר אותה לפרונט.

---

## מה חייב להשתנות בפרונט (Checklist מחייב)

1. להחליף קריאה מ־`/demo_predict` ל־`/predict/daily`.
2. להחליף request model לטריגר מינימלי:
   - `userId`
   - `date` בפורמט `yyyy-MM-dd`
3. להחליף response model למבנה production (`risk_score`, `risk_level`, `recommendation`, `data_quality_*`, `meta`).
4. לחשב אחוז תצוגה רק בצד פרונט:
   - `finalRiskScore = round(risk_score * 100)`
5. להניח שהבקאנד שומר אוטומטית את תוצאת החיזוי ב־Firestore (`daily_health/{date}`); אין כתיבה עסקית כפולה מהפרונט.
6. להסיר תלות עסקית ב־`/demo_predict` (להשאיר רק לדמו/בדיקות אם צריך).

---

## חוזה API מעודכן לפרונט

### Request (חובה) — `POST /predict/daily`

```json
{
  "userId": "firebase_uid",
  "date": "2026-05-09"
}
```

### Response (חובה)

```json
{
  "risk_level": "Medium",
  "risk_score": 0.4182,
  "recommendation": "Moderate risk: ... Confidence: medium ...",
  "data_quality_score": 0.73,
  "data_quality_status": "Good",
  "meta": {
    "model_version": "ExtraTrees",
    "fallback_reason": "none",
    "confidence_bucket": "Medium"
  }
}
```

---

## כתיבה ל־Firestore לאחר חיזוי

נשמרים אוטומטית ע"י הבקאנד ב־`daily_health/{date}`:

- `finalRiskScore` (מספר 0..100)
- `riskLevel` (`Low/Medium/High`)
- `backendRecommendation`
- `dataQualityScore`
- `dataQualityStatus`
- `predictionMeta` (אובייקט `meta` מלא)
- `predictionUpdatedAt` (server timestamp)

הערה: הכתיבה בשרת היא מקור האמת. בפרונט אפשר לשמור cache מקומי בלבד (אופציונלי) ולא לבצע כתיבת merge עסקית נוספת לאותו מידע.

---

## טריגר עסקי מומלץ (למניעת כפילויות)

- טריגר ראשי: מיד אחרי הצלחה בשמירת `daily_checkins/{date}`.
- טריגר משני (אופציונלי): בכניסה לדשבורד רק אם אין תוצאה עדכנית להיום.
- כלל idempotency פרונט:
  - אם קיים כבר `predictionUpdatedAt` להיום ואין שינוי בנתוני היום מאז — לא לקרוא שוב.
- כלל idempotency בקאנד (לסגירה בפגישה):
  - להחליט אם מוסיפים `predictionRequestId`/hash כדי למנוע write כפול ב-retry bursts.
- timeout וריטריי:
  - timeout רשת ברור.
  - retry ידני עם CTA, לא retry אינסופי אוטומטי.

---

## טיפול שגיאות UX

- `500` עם `insufficient_input_quality`:
  - להציג הודעה ידידותית: "חסרים נתוני יום (שינה/עומס/סנכרון). נסה שוב לאחר סנכרון."
  - לא להציג ציון חדש אם הקריאה נכשלה.
- `500` עם `model_not_live:*`:
  - להציג הודעת שירות זמני לא זמין.
  - לשמור event לניטור.
- כשל רשת/timeout:
  - להציג מצב שגיאה ברור + כפתור ניסיון חוזר.
  - לשמור את ה־UI קונסיסטנטי (ללא "טעינה" תקועה).

---

## אילו נתונים הפרונט חייב לוודא שנשמרים כל יום

הפרונט לא שולח אותם ב־`/predict/daily`, אבל חייב לוודא שהם קיימים ב־Firestore כדי לשפר איכות חיזוי:

- `daily_health`:
  - `sleepMinutes`
  - `steps` או `distanceMeters`
  - `activeCalories` (אם זמין)
  - `heartRateAvg`/`heartRateMin` (אם זמין)
- `daily_checkins`:
  - `stressLevel`
  - `muscleSoreness`
  - `energyLevel` (אם קיים במסך)
- `daily_nutrition` (אם מודול תזונה פעיל):
  - `totalProtein`
  - `totalCarbs`
  - `mealsLoggedCount`

---

## מה לא עושים בפרונט

- לא מחשבים פיצ'רים הנדסיים (`acwr_ratio`, `sleep_debt_3d`, וכו').
- לא בונים payload מלא ידנית עבור מסלול הייצור היומי.
- לא מנחשים ספי סיכון מקומית; משתמשים אך ורק בתשובת השרת.

---

## לוגים וניטור תקלות (Frontend + Backend)

### Backend (הכי חשוב לתקלות מערכת)

- מקור האמת לתקלות serving הוא הבקאנד.
- כבר היום קיימים לוגים אפליקטיביים בקבצי log (`logs/athleagent.log`) כולל:
  - איכות דאטה (`predict_data_quality`)
  - חסימות איכות (`predict_blocked`)
  - שגיאות route (`predict_daily_route_error`, `predict_route_error`)
- מומלץ להוסיף/להשלים:
  - `request_id` לכל קריאה (קורלציה בין שרת וקליינט).
  - structured logs (JSON) לסביבת production.
  - alerting על קפיצה בשיעור `500` ו־`insufficient_input_quality`.

### Frontend (חשוב לחוויית משתמש ודיבאג קליינט)

- מומלץ לייצר event logs קליינטים, לדוגמה:
  - `prediction_triggered`
  - `prediction_success`
  - `prediction_failed`
  - `prediction_saved_to_firestore`
- בכל event לשמור:
  - `userId` (או hash מזהה)
  - `date`
  - `http_status`
  - `error_type`
  - `latency_ms`
  - `model_version` אם התקבל

החלטה מקצועית: ניטור תקלות מערכת = קודם כל Backend; ניטור UX/כשלים במכשיר = Frontend. בפועל צריך את שניהם.

---

## בדיקות חיבור Firebase (חובה לפני Go-Live)

מטרת הסעיף: לוודא שהבקאנד באמת יכול לקרוא ולכתוב ל־Firestore בסביבת ההרצה.

### מה חייב להיות מוגדר

- קובץ Service Account JSON תקין של אותו Firebase Project.
- אחד ממשתני הסביבה:
  - `FIREBASE_SERVICE_ACCOUNT_KEY` (נתיב לקובץ JSON)
  - או `GOOGLE_APPLICATION_CREDENTIALS` (נתיב לקובץ JSON)
- הרשאות IAM מתאימות לחשבון השירות (קריאה/כתיבה ל־Firestore).

### בדיקות מהירות בפועל

1. להפעיל backend עם משתנה סביבה מוגדר.
2. לשלוח `POST /predict/daily` עם `userId+date` אמיתיים.
3. לוודא 3 דברים:
   - מתקבלת תשובת 200 עם `risk_score`.
   - במסמך `users/{uid}/daily_health/{date}` מתעדכנים `finalRiskScore`, `riskLevel`, `predictionMeta`, `predictionUpdatedAt`.
   - בלוגים אין שגיאות `firestore_snapshot_unavailable` או `prediction_persist_failed`.

### תקלות נפוצות

- Service account מפרויקט אחר -> קריאות/כתיבות "מוזרות" או כשל הרשאות.
- נתיב JSON לא תקין בסביבת הרצה -> אין Firestore client.
- סביבה מקומית עובדת אבל שרת בדמו/ענן לא (env var לא הוגדר שם).

---

## נושאים לסגירה בפגישת תיאום (Frontend + Backend)

הסעיף הזה הוא agenda פרקטי, לפי סדר חשיבות.

1. **מקור אמת נתונים**
   - מוסכם: Firestore הוא מקור האמת, והבקאנד מושך נתונים בעצמו ב־`/predict/daily`.
   - לא מעבירים payload חלקי מהפרונט לזרימה היומית.

2. **בעלות על כתיבה ל־DB**
   - מוסכם: הכתיבה העסקית של תוצאת חיזוי מתבצעת בבקאנד בלבד.
   - הפרונט לא מבצע merge כפול לאותם שדות.

3. **טריגרים וזמני הפעלה**
   - טריגר ראשי אחרי שמירת `daily_checkins`.
   - האם להפעיל טריגר נוסף אחרי `daily_health`/`daily_nutrition` כשהם מגיעים מאוחר יותר באותו יום.

4. **מדיניות Retry / Idempotency**
   - לקבוע retry policy אחידה.
   - להחליט האם מוסיפים `predictionRequestId` בבקשה למניעת כפילויות.

5. **UX במצבי כשל**
   - טקסטים סופיים ל־`insufficient_input_quality`, `model_not_live`, network timeout.
   - האם מציגים "ציון אחרון" עם סימון שהוא לא עדכני.

6. **ניטור ו-Observability**
   - אילו אירועים נמדדים בפרונט ובאילו שמות.
   - אילו alerts יוגדרו בבקאנד (על 500s / ירידת data quality / persist failures).

7. **Done Definition מוסכמת**
   - תנאי קבלה סופיים (סעיף הבא במסמך) לפני merge ל-main.

---

## חלוקת עבודה ברורה לפגישה (מי עושה מה)

### מה השותף בפרונט נדרש להוסיף/לשנות

1. **החלפת endpoint**
   - לעבור מ־`/demo_predict` ל־`POST /predict/daily`.
2. **עדכון מודלים באנדרואיד**
   - Request: `userId`, `date` בלבד.
   - Response: `risk_score`, `risk_level`, `recommendation`, `data_quality_score`, `data_quality_status`, `meta`.
3. **לוגיקת טריגר**
   - להפעיל חיזוי אחרי שמירת `daily_checkins/{date}`.
   - למנוע קריאות כפולות אם אין שינוי נתונים להיום.
4. **UX לשגיאות**
   - מצבי UI מסודרים ל־`insufficient_input_quality`, `model_not_live`, ו־network timeout.
5. **Telemetry בפרונט**
   - להוסיף אירועים: `prediction_triggered`, `prediction_success`, `prediction_failed`.
   - לשלוח `latency_ms`, `http_status`, `error_type`.

### מה אתה נדרש להוסיף/לשנות בבקאנד

1. **יציבות ושרת**
   - לוודא ש־`POST /predict/daily` הוא הזרימה היציבה והפעילה בסביבת היעד.
2. **לוגים תפעוליים**
   - להחזיק קובץ לוג פעיל ב־`logs/athleagent.log`.
   - לוודא שהלוגים הקריטיים קיימים בפועל: `predict_data_quality`, `predict_blocked`, `predict_daily_route_error`.
3. **Persist ל־Firestore**
   - לוודא שבכל קריאה תקינה נשמרים `finalRiskScore`, `riskLevel`, `backendRecommendation`, `predictionMeta`, `predictionUpdatedAt`.
4. **Idempotency/Retry policy**
   - להחליט ולתעד מדיניות ל־retry bursts (אופציונלית: `predictionRequestId`/hash).
5. **Monitoring**
   - להגדיר בדיקות ואלרטים על:
     - קפיצה ב־HTTP 500.
     - קפיצה ב־`insufficient_input_quality`.
     - כשלים בכתיבה ל־Firestore.

### סדר עבודה מומלץ ביניכם

1. הפרונט מעדכן contract וטריגרים.
2. הבקאנד מאמת לוגים + Firebase persist בסביבת היעד.
3. מריצים יחד את "תוכנית בדיקות אינטגרציה משותפת" מהמסמך.
4. סוגרים Definition of Done ורק אז merge.

---

## תוכנית בדיקות ידנית קצרה (לפרונט)

1. מילוי סקר בוקר מלא -> לוודא קריאה ל־`/predict/daily` ושמירת תוצאה מלאה ב־`daily_health/{date}` ע"י הבקאנד.
2. נתוני wearable חלקיים -> לוודא או תוצאה עם quality נמוך או הודעת איכות מתאימה.
3. פתיחת דשבורד פעמיים באותו יום -> לוודא שאין קריאות כפולות ללא שינוי נתונים.
4. ניתוק רשת בזמן קריאה -> לוודא הודעת שגיאה ו־retry ידני תקין.
5. לוודא שהגרף ההיסטורי ממשיך להתבסס על `finalRiskScore` (7 ימים אחרונים).

---

## תוכנית בדיקות אינטגרציה משותפת (לפגישה)

1. **Happy path מלא**
   - סקר נשמר -> `POST /predict/daily` -> תשובה תקינה -> DB מתעדכן.
2. **חסרים בנתוני היום**
   - לבדוק שהבקאנד משתמש בהיסטוריה כשאפשר או מחזיר שגיאת איכות ברורה כשאי אפשר.
3. **Retry כפול מאותו מכשיר**
   - לוודא שאין פגיעה בעקביות הנתונים במסמך היום.
4. **שני טריגרים קרובים בזמן**
   - לבדוק מי מנצח ומה נשמר בסוף (עקביות `predictionUpdatedAt`).
5. **בדיקת סביבת יעד**
   - להריץ בדיקה זהה גם בסביבת staging/השרת האמיתי, לא רק מקומית.

---

## הגדרת Done לפרונט

- אין יותר תלות עסקית ב־`/demo_predict`.
- כל קריאת ייצור יומית עוברת דרך `POST /predict/daily`.
- מסך הדשבורד מציג תוצאת production בלבד.
- תוצאת החיזוי וה־meta נשמרות בצורה עקבית ב־Firestore.
- קיימים לוגים בסיסיים בקליינט + יכולת ניטור בצד שרת.

## הגדרת Done מערכתית (Frontend + Backend)

- `POST /predict/daily` פעיל בסביבת היעד עם חיבור Firebase תקין.
- השרת גם מחזיר תוצאה לפרונט וגם שומר אותה ל־Firestore בכל קריאה תקינה.
- אין תלות עסקית ב־`/demo_predict`.
- קיימת מדיניות retry/idempotency מוסכמת ומתועדת.
- כל תרחישי האינטגרציה הקריטיים עברו בבדיקות משותפות.
