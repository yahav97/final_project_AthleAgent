# AthleAgent — נתוני DB לספורטאי (מצב נוכחי מול מצב יעד)

> **הבהרה:** "DB" במסמך זה = **Firestore** בלבד. אין שימוש ב-PostgreSQL בבקאנד הנוכחי; תוצאות חיזוי נשמרות במסמכי `daily_health` יחד עם שאר שדות היום.

מסמך זה עושה סדר בנושא הנתונים לכל ספורטאי ב-Firestore:
- מה נשמר היום בפועל
- מי כותב כל שדה
- איך מתבצע שימוש יומי והיסטוריה
- האם יש מחיקה אחרי 7 ימים
- מה המצב הרצוי (Target State)

---

## 1) מבנה הנתונים לספורטאי (Firestore)

לכל ספורטאי (`uid`) נשמרים המסמכים הבאים:

- `users/{uid}`  
  פרופיל בסיסי (לדוגמה: `age`, `vo2Max`, `historyInjuryCount`).

- `users/{uid}/daily_health/{yyyy-MM-dd}`  
  נתוני Health יומיים + תוצאת חיזוי יומית.

- `users/{uid}/daily_checkins/{yyyy-MM-dd}`  
  דיווח עצמי יומי (סטרס, כאב שרירים, אנרגיה).

- `users/{uid}/daily_nutrition/{yyyy-MM-dd}`  
  אגרגציית תזונה יומית.

ה-key של המסמך היומי הוא תאריך (`yyyy-MM-dd`), לכן בפועל יש מסמך נפרד לכל יום.

---

## 2) מה נשמר היום בפועל (Current State)

### 2.1 `daily_health/{date}` — נתוני יום + תוצאות חיזוי

**Raw signals** (מהאפליקציה/סנכרון):  
`sleepMinutes`, `steps`, `distanceMeters`, `activeCalories`, `totalCalories`, `heartRateAvg`, `heartRateMax`, `heartRateMin`, `weightKg`, `bmrCalories`.

**Prediction output** (מהבקאנד לאחר חיזוי מוצלח):  
- `finalRiskScore` (0-100)
- `riskLevel`
- `backendRecommendation` — טקסט המלצת ה-ML מהבקאנד (תבניות קבועות לפי הסתברות מודל + ACWR + משפט confidence להיסטוריה); זהה לשדה `recommendation` בתשובת `POST /predict` / `POST /predict/daily`. לא נוצר בצד הלקוח.
- `dataQualityScore`
- `dataQualityStatus`
- `predictionMeta`
- `predictionUpdatedAt`

(ייתכן שבאותו מסמך קיימים גם שדות אחרים מהאפליקציה, למשל טקסט מ-Gemini ל-UI — שדה נפרד, לא חלק מחוזה המודל.)

### 2.2 `daily_checkins/{date}`

שדות עיקריים:
- `stressLevel`
- `muscleSoreness`
- `energyLevel`

### 2.3 `daily_nutrition/{date}`

שדות עיקריים:
- `totalProtein`
- `totalCarbs`
- `mealsLoggedCount`

### 2.4 `users/{uid}` (profile)

שדות רלוונטיים לחיזוי:
- `age`
- `vo2Max` (או `vo2_max`)
- `historyInjuryCount` (או `history_injury_count`)

---

## 3) איך זה עובד בכל יום

1. פרונט (במצב היעד) שולח `userId + date` ל-`POST /predict/daily`.
2. בקאנד טוען ישירות מ-Firestore את:
   - `users/{uid}`
   - `daily_health/{date}`
   - `daily_checkins/{date}`
   - `daily_nutrition/{date}`
3. בקאנד עושה preprocessing + feature engineering + history enrichment.
4. הבקאנד מריץ מודל.
5. הבקאנד שומר חזרה ל-`daily_health/{date}` את תוצאת החיזוי (merge write).

הערה: `merge` אומר שמעדכנים/מוסיפים שדות בלי למחוק שדות אחרים במסמך.

---

## 4) האם יש מחיקה אוטומטית אחרי 7 ימים?

**לא. במצב הנוכחי אין מחיקה אוטומטית של ימים ישנים.**

מה שקיים כיום:
- הבקאנד משתמש בחלון היסטוריה של 7 ימים לצורך חישובי מודל (lookback).
- ה-UI מציג לרוב רק 7 ימים אחרונים בגרף.

מה זה *לא* אומר:
- זה לא אומר ש-Firestore מוחק נתונים אחרי 7 ימים.
- אין כרגע job/TTL פעיל בבקאנד שמנקה אוטומטית מסמכים ישנים.

---

## 5) הבחנה חשובה: "חלון חישובי" מול "Retention"

- **חלון חישובי (Computation Window):**  
  כמה ימים אחורה המודל מסתכל (כיום: 7).

- **Retention Policy:**  
  כמה זמן שומרים נתונים בפועל ב-DB (כיום: לא מוגבל בקוד/ללא ניקוי אוטומטי).

אלה שני דברים שונים, וחשוב לא לערבב ביניהם.

---

## 6) מצב יעד מומלץ (Target State)

### 6.1 ארכיטקטורת קריאה/כתיבה

- פרונט שולח רק `userId + date` ל-`/predict/daily`.
- בקאנד הוא מקור האמת לטעינת הנתונים, חישוב הפיצ'רים והרצת המודל.
- הבקאנד הוא מקור האמת גם ל-persist של תוצאת החיזוי.

### 6.2 Retention מומלץ

כדי לאזן עלות, audit ויכולת למידה:

- `daily_health`, `daily_checkins`, `daily_nutrition`: לשמור לפחות `90-180` יום.
- תוצאת חיזוי יומית (`finalRiskScore` וכו'): לשמור לפחות `180` יום (עדיף `365` אם העלות מאפשרת).
- פרופיל משתמש (`users/{uid}`): ללא מחיקה אוטומטית, רק לפי GDPR/account deletion policy.

אם מחליטים לשמור רק 7 ימים:
- מאבדים יכולת ניתוח מגמות עונתיות, תחקור אירועים, וטיוב מודל ארוך טווח.
- לכן 7 ימים מתאים לחלון חישובי, לא כמדיניות retention.

### 6.3 אם בכל זאת רוצים TTL

להגדיר זאת במפורש כמדיניות נפרדת:
- שדה `expiresAt` לכל מסמך יומי.
- TTL policy ב-Firestore (או job מתוזמן).
- להחריג שדות/קולקשנים שנדרשים לאנליטיקה ארוכת טווח.

---

## 7) פערים ידועים מול היעד

- בפרונט הנוכחי עדיין קיימת קריאת legacy ל-`/demo_predict` בחלק מהמסכים.
- ביעד, כל המסכים צריכים להתיישר ל-`/predict/daily` בלבד.
- חשוב ליישר שפה בין מסמכים: "7 ימים" = חלון חישובי, לא מחיקה מה-DB.

---

## 8) החלטות מוצר/דאטה שצריך לנעול

1. מה retention הרשמי לכל collection (ימים/חודשים).
2. האם נדרש TTL אוטומטי או שמירת היסטוריה מלאה.
3. מה תקופת audit מינימלית לחיזויים לצרכי QA/חקירה.
4. מי owner לכל שדה (Frontend/Backend) כדי למנוע כפילויות.

---

## 9) סיכום קצר

- כיום: שומרים נתונים יומיים לפי תאריך; אין מחיקה אוטומטית אחרי 7 ימים.
- 7 ימים היום משמשים לחלון היסטוריה בחישוב ובהצגה בלבד.
- יעד נכון: `/predict/daily` כנתיב יחיד, הבקאנד מושך את כל הנתונים מה-DB, ומדיניות retention נקבעת בנפרד וברורה.
