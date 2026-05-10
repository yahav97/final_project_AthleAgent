# AthleAgent — מסמך פגישת תיאום Frontend/Backend (HE)

מטרת המסמך: לסגור החלטות אינטגרציה, חלוקת אחריות, ותוכנית ביצוע ברורה בין צד הפרונט לצד הבקאנד.

## 1) מטרת הפגישה

ליישר מעבר מלא לזרימת חיזוי יומית יציבה:

- פרונט שולח טריגר מינימלי.
- בקאנד מושך נתונים מ-Firestore, מריץ מודל, מחזיר ושומר תוצאה.
- אין פיצול לוגיקה עסקית או כתיבה כפולה.

## 2) חוזה עבודה מוסכם

### Endpoint ייצור

- `POST /predict/daily`

### Request

```json
  "userId": "firebase_uid",
```

"date": "yyyy-MM-dd"

}

### Response (עיקרי)

- `risk_score`
- `risk_level`
- `recommendation` (טקסט מהבקאנד; אותו תוכן נשמר ב-Firestore תחת `backendRecommendation`)
- `data_quality_score`
- `data_quality_status`
- `meta`

## 3) חלוקת אחריות ברורה

### אחריות פרונט

1. להפעיל טריגר אחרי שמירת check-in יומי.
2. לשלוח `userId + date` בלבד ל-`/predict/daily`.
3. להציג תשובת שרת בצורה עקבית ב-UI.
4. למנוע קריאות כפולות ללא שינוי נתונים.
5. לטפל במצבי שגיאה בצורה ידידותית (quality/model_not_live/network).

### אחריות בקאנד

1. למשוך snapshot יומי + פרופיל מ-Firestore.
2. לבצע preprocessing + history enrichment + quality scoring.
3. להחזיר `InjuryPredictionResponse` תקין.
4. לשמור תוצאה ל-`daily_health/{date}` כ-source of truth.
5. לרשום לוגים תפעוליים מסודרים לתחקור.

## 4) נושאים שחייבים להיסגר בפגישה

1. **טריגרים:** רק אחרי check-in, או גם אחרי sync/meal מאוחרים?
2. **Idempotency:** האם מוסיפים `predictionRequestId` או hash לבקשה?
3. **Retry policy:** כמה ניסיונות, ובאיזה תנאים?
4. **UX כשלים:** טקסטים סופיים ומצבי מסך לכל סוג שגיאה.
5. **Telemetry:** אילו אירועים נשמרים בפרונט, ואילו לוגים מחייבים בבקאנד.

## 5) תוכנית בדיקות משותפת

1. Happy path מלא: check-in -> predict/daily -> response -> Firestore update.
2. נתונים חלקיים: התנהגות quality תקינה (תוצאה עם איכות נמוכה או חסימה).
3. retry כפול: אין חוסר עקביות במסמך היום.
4. כשל רשת: UX ברור + retry ידני תקין.
5. בדיקה בסביבת יעד (ולא רק מקומית).

## 6) משימות פעולה אחרי הפגישה

### פרונט

- אימות שאין קריאות ל-`POST /predict` (הוסר מהבקאנד); רק `POST /predict/daily` נתמך ב-HTTP.
- החלפה מלאה מ-`/demo_predict` ל-`/predict/daily`
- התאמת models של request/response
- מנגנון מניעת טריגר כפול
- UX שגיאות מוסכם

### בקאנד

- אימות persist מלא בכל קריאה תקינה
- לוגים ואבחון כשלים ברורים
- מדיניות retry/idempotency מתועדת
- בדיקת חיבור Firebase בכל סביבת הרצה

## 7) Definition of Done משותף

- אין תלות עסקית ב-`/demo_predict`.
- כל חיזוי יומי עובר דרך `POST /predict/daily`.
- תשובה נשמרת עקבית ב-Firestore ומוצגת נכון בפרונט.
- כל תרחישי האינטגרציה הקריטיים עברו.
- יש יכולת תחקור תקלות מלאה (frontend events + backend logs).

