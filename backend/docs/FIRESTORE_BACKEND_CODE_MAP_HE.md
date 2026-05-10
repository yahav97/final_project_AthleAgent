# מפת גישה ל-Firestore מהבקאנד — נגזר מקוד בלבד

מסמך זה מתאר **את מה שהקוד בפועל עושה**: מחרוזות נתיב (`collection` / `document`), מפתחות שדות ב-exact spelling, וקריאה מול כתיבה. אין כאן הסקות ממסכי אפליקציה או ממסמכי תיאור חיצוניים.

**קבצי מקור עיקריים**

| קובץ | תפקיד |
|------|--------|
| [`services/history_service.py`](../services/history_service.py) | אתחול Firebase Admin, קריאת snapshot יומי, סטרימינג היסטוריה, כתיבת תוצאות חיזוי |
| [`services/prediction_service.py`](../services/prediction_service.py) | מיפוי מילוני `profile` / `daily_health` / `daily_checkins` / `daily_nutrition` ל־`InjuryPredictionRequest` |
| [`services/preprocessing.py`](../services/preprocessing.py) | שימוש בשמות השדות של `InjuryPredictionRequest` אחרי `model_dump()` (לא ישירות מול Firestore) |
| [`schemas/inference.py`](../schemas/inference.py) | הגדרת שמות השדות של הבקשה הפנימית (camelCase לצד `snake_case` לפרופיל) |

קובץ [`external/firestore_history.py`](../external/firestore_history.py) מכיל גם גישה ל־`users` / `daily_health` / `daily_checkins`, אבל **אין ייבוא אליו** מנתיבי ה-API / השירותים הפעילים — לא חלק משרשרת הייצור הנוכחית.

---

## 1. נתיבי מסמכים ב-Firestore (מחרוזות כמו בקוד)

מזהה יום: פרמטר `date_key` בפורמט **`yyyy-MM-dd`** (מחרוזת), כפי שמגיע מ־API (`DailyPredictionTriggerRequest.date`).

| פעולה | נתיב |
|--------|------|
| קריאת פרופיל | `collection("users").document(user_id)` |
| קריאת בריאות יומית | `...collection("daily_health").document(date_key)` |
| קריאת צ׳ק-אין יומי | `...collection("daily_checkins").document(date_key)` |
| קריאת תזונה יומית | `...collection("daily_nutrition").document(date_key)` |
| כתיבת תוצאות חיזוי (merge) | אותו נתיב כמו `daily_health` לעיל |

סטרימינג להיסטוריה (`fetch_user_history`): על אותו `user_ref` — `collection("daily_health").stream()` ו־`collection("daily_checkins").stream()` (כל המסמכים באוסף המשנה; סינון לפי טווח תאריכים בפייתון).

**מה הבקאנד לא נוגע בו בקוד:** אוסף `teams`, תת־אוסף `meals`, או מסמכים שלא נסרקים בפונקציות למעלה.

---

## 2. קריאה — `fetch_daily_firestore_snapshot`

מחזיר מבנה עם ארבעה מפתחות ברמת המילון החיצוני (קבועים בקוד):

- `"profile"` — תוכן `users/{uid}` או `{}` אם אין מסמך
- `"daily_health"` — תוכן `daily_health/{date_key}` או `{}`
- `"daily_checkins"` — תוכן `daily_checkins/{date_key}` או `{}`
- `"daily_nutrition"` — תוכן `daily_nutrition/{date_key}` או `{}`

אין קריאה לתת־אוסף `meals`; כל שדה שקיים רק שם **לא** נכנס לחיזוי דרך הקוד הנוכחי.

---

## 3. מיפוי לשדות שמשתמשים בהם בחיזוי (`predict_injury_risk_from_firestore`)

המיפוי מוגדר ב־[`prediction_service.py`](../services/prediction_service.py) (קריאות `.get("...")`).

### `users/{uid}` → פרופיל

| מפתח ב-Firestore (מחרוזת בקוד) | הערות |
|----------------------------------|--------|
| `age` | |
| `historyInjuryCount` **או** `history_injury_count` | |

### `daily_health/{date}`

| מפתח ב-Firestore |
|------------------|
| `sleepMinutes` |
| `steps` |
| `distanceMeters` |
| `activeCalories` |
| `totalCalories` |
| `heartRateAvg` |
| `heartRateMax` |
| `heartRateMin` |
| `weightKg` |
| `bmrCalories` |

### `daily_checkins/{date}`

| מפתח ב-Firestore |
|------------------|
| `energyLevel` |
| `muscleSoreness` |
| `stressLevel` |

### `daily_nutrition/{date}`

| מפתח ב-Firestore |
|------------------|
| `totalProtein` |
| `totalCarbs` |
| `mealsLoggedCount` |

**שדות ידועים שלא נמשכים בפונקציה הזו:** למשל `totalCalories` על מסמך התזונה (שונה מ־`totalCalories` ב־`daily_health`), כל שדה בשם `avgHeartRate`, וכל שדה נוסף במסמכים — הקוד **מתעלם** מהם בשלב האסsembl של `InjuryPredictionRequest` (עם `extra="ignore"` ברמת המודל רק לשדות נוספים אם היו נכנסים דרך מודל אחר; כאן הבנייה היא ידנית ולא ממילוי אוטומטי של המסמך הגולמי).

---

## 4. שימוש בשדות אחרי המיפוג — `preprocessing.py` / איכות נתונים

אחרי בניית `InjuryPredictionRequest`, הקוד משתמש ב־`payload.model_dump()`:

- **איכות נתונים** (`calculate_data_quality_score`): בודק במפורש את  
  `userId`, `date`,  
  `sleepMinutes`, `steps`, `distanceMeters`, `heartRateAvg`,  
  `stressLevel`, `muscleSoreness`,  
  וכן לוגיקת `load_signal` / `recovery_signal` מבוססת `steps` / `distanceMeters` / `sleepMinutes` / זוג צ׳ק-אין.

- **הנדסת פיצ’רים לדאטאפריים** (`injury_request_to_model_dataframe`): קורא מהמילון המאוחד (שמות כמו בטבלאות למעלה) בין השאר:  
  `age`, `history_injury_count`,  
  `sleepMinutes`, `steps`, `distanceMeters`, `activeCalories`, `totalCalories`, `bmrCalories`,  
  `totalProtein`, `totalCarbs`, `mealsLoggedCount`,  
  `weightKg`, `heartRateAvg`, `heartRateMin`,  
  `stressLevel`, `muscleSoreness`.  

שדות כמו `heartRateMax` מסומנים כ־**סובלניים** לחוסר (`TOLERANT_FIELDS`) ולא נכנסים לנוסחאות המספריות העיקריות כמו דופק מנוחה.

---

## 5. היסטוריה — מיזוג שורות יום (`fetch_user_history`)

לכל תאריך בחלון, השורה המאוחדת היא `dict(health_doc) | dict(checkin_doc)` בתוספת `date_key`.  
פונקציות העזר ב־[`history_service.py`](../services/history_service.py) קוראות מהשורה המאוחדת לפחות את:

`distanceMeters`, `steps`, `sleepMinutes`, `heartRateMin`, `heartRateAvg`

(לצורך חישובי עומס / שינה / HRV פרוקסי בגלילה.)

---

## 6. כתיבה — `save_daily_prediction_result`

כתיבה ב־**merge** ל־`users/{uid}/daily_health/{date_key}` עם מפתחות **בדיוק**:

| מפתח ב-Firestore | מקור בערך (`result` מהחיזוי) |
|------------------|-------------------------------|
| `finalRiskScore` | `round(risk_score * 100, 2)` כאשר `risk_score` מ־`predict_injury_risk` |
| `riskLevel` | `risk_level` |
| `dataQualityScore` | `data_quality_score` |
| `dataQualityStatus` | `data_quality_status` |
| `predictionUpdatedAt` | `datetime.utcnow().isoformat()` |

התגובה של `predict_injury_risk` **לא** כוללת `recommendation`; בהתאמה, **אין כתיבה** של `backendRecommendation` או דומה בפונקציה זו בקוד הנוכחי.

---

## 7. סיכום לצריכת שדות בבקאנד

- כדי שהשרת יקרא ערך מה-Firestore בזרימת `/predict/daily`, השם חייב להופיע באחת מטבלאות הסעיפים **3–5** לפי מסמך המקור.
- שינוי שם שדה באפליקציה (למשל `avgHeartRate` במקום `heartRateAvg`) ללא עדכון הקוד → הערך **לא** ייכנס לחיזוי.
- הרחבות עתידיות: להוסיף מפתח ל־`InjuryPredictionRequest` + ל־`predict_injury_risk_from_firestore` + ללוגיקה ב־`preprocessing` לפי הצורך.
