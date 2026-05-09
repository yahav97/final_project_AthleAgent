# AthleAgent — סיכום קצר לפגישת תיאום (Prediction Migration)

## החלטה ארכיטקטונית (מוסכם)

- נתיב ייצור יומי: `POST /predict/daily`
- הפרונט שולח רק: `userId`, `date`
- הבקאנד:
  - מושך נתוני יום + פרופיל מ־Firestore
  - מריץ מודל
  - מחזיר תוצאה לפרונט
  - שומר תוצאה ל־DB (`daily_health/{date}`)

## חלוקת אחריות

- **Frontend**
  - מפעיל טריגר אחרי שמירת צ'ק-אין
  - מציג את תגובת השרת
  - לא מבצע כתיבה עסקית כפולה של תוצאת חיזוי
- **Backend**
  - מקור האמת לחיזוי ולשמירת התוצאה
  - טיפול באיכות דאטה והיסטוריה
  - לוגים ושגיאות מערכת

## מה חייב להיסגר בפגישה

1. טריגרים: רק אחרי check-in או גם אחרי sync/meal מאוחרים?
2. Retry + Idempotency: האם מוסיפים `predictionRequestId`?
3. UX לשגיאות: נוסח סופי ל־`insufficient_input_quality` / `model_not_live`.
4. ניטור: אילו אירועים נמדדים בפרונט ובבקאנד.

## בדיקות חובה לפני Go-Live

1. חיבור Firebase לבקאנד:
   - `FIREBASE_SERVICE_ACCOUNT_KEY` או `GOOGLE_APPLICATION_CREDENTIALS`
2. תרחיש מלא:
   - שמירת סקר -> קריאה ל־`/predict/daily` -> תשובת 200 -> עדכון מסמך יום ב־Firestore
3. בדיקות כשל:
   - נתונים חסרים / ניתוק רשת / retry כפול

## Definition of Done (קצר)

- אין תלות עסקית ב־`/demo_predict`
- `POST /predict/daily` פעיל בסביבת היעד
- השרת גם מחזיר וגם שומר תוצאה בכל קריאה תקינה
- תרחישי האינטגרציה הקריטיים עברו
