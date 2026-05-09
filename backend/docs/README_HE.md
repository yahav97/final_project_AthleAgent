# AthleAgent Backend Docs (HE)

מטרת הסט הזה: לתת תמונה מלאה ומדויקת על הבקאנד, בלי עומס מסמכים.

## ארכיטקטורת נתונים והמלצת ML (מעודכן)

- **אחסון אפליקציה:** רק **Firestore** (אין PostgreSQL או SQLAlchemy בבקאנד היום). מסמכי יום, פרופיל ותוצאות חיזוי חיים תחת `users/{uid}/...`.
- **טקסט ההמלצה של המודל (`recommendation` ב-API, `backendRecommendation` ב-Firestore):** נוצר **בבקאנד** בלבד (`prediction_service`), לא בפרונט. אחרי חיזוי מוצלח הוא נשמר ב-merge ל-`daily_health/{date}` יחד עם `finalRiskScore`, `riskLevel` ושדות איכות.
- **לוגיקה:** תבניות טקסט קבועות (אנגלית) לפי **הסתברות המודל** ו-**יחס עומס ACWR** מהשורה המחושבת, ואז נוספת **הערת Confidence** לפי זמינות היסטוריה (7 ימים). זה דטרמיניסטי — אפשר לשחזר מאותם קלטים.
- **הבחנה:** באנדרואיד עשויה להופיע בנפרד המלצת ניסוח מ-**Gemini** (שדה כמו `aiRecommendation`) לצורכי UI/מאמן; זה **לא** מקור האמת של חוזה ה-ML ולא מחליף את `backendRecommendation`.

## מה קוראים ובאיזה סדר

1. `ONBOARDING_BACKEND_ML_HE.md`  
   מסמך היכרות מלא עם הארכיטקטורה, זרימת הנתונים, שכבת ה-ML, endpoints ונהלי עבודה.
2. `ATHLETE_DB_DATA_LIFECYCLE_HE.md`  
   מה נשמר ב-Firestore לכל ספורטאי, איך נשמר יומית, חלון היסטוריה מול retention, ומה מצב היעד.
3. `PROTOTYPE_PRESENTATION_PREP_HE.md`  
   מסמך הכנה להצגת פרוטוטייפ (תסריט, מסרים, Q&A, checklist).
4. `FRONTEND_BACKEND_SYNC_MEETING_HE.md`  
   מסמך פגישת תיאום עם השותף בפרונט (חלוקת אחריות, החלטות, DoD ובדיקות).
5. `DATA_CONTRACT_FRONTEND_BACKEND.md`  
   חוזה נתונים פורמלי (EN) בין Firestore/Frontend לבין ה-Backend לחיזוי.

## מה לא צריך יותר

- המסמכים הישנים תחת `docs/` ברמת הפרויקט שאיחדו אליהם תוכן, הוחלפו בסט מרוכז זה.
- מסמכים תחת `docs/` (למשל `BACKEND_ARCHITECTURE.md`) עשויים לכלול **אפיון היסטורי** (PostgreSQL, מפת endpoints מורחבת). למצב היישום בפועל עדיפים המסמכים כאן ב-`backend/docs/`.
- אם צריך להוסיף מסמך חדש, קודם בודקים שהמידע לא מתאים לאחד משלושת המסמכים הקיימים.

## כללי עדכון

- כל שינוי ב-API חיזוי (`/predict`, `/predict/daily`) מחייב עדכון ב-`DATA_CONTRACT_FRONTEND_BACKEND.md`.
- כל שינוי תפעולי/ארכיטקטוני בבקאנד או ב-ML מחייב עדכון ב-`ONBOARDING_BACKEND_ML_HE.md`.
- כל שינוי במבנה/מדיניות שמירת נתונים ב-Firestore מחייב עדכון ב-`ATHLETE_DB_DATA_LIFECYCLE_HE.md`.
- כל שינוי בתהליך הדמו מחייב עדכון ב-`PROTOTYPE_PRESENTATION_PREP_HE.md`.
- כל שינוי החלטות אינטגרציה מול הפרונט מחייב עדכון ב-`FRONTEND_BACKEND_SYNC_MEETING_HE.md`.
