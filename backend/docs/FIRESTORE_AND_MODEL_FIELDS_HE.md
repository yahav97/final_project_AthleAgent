# שדות Firestore לעומת שדות המודל

מסמך זה מרכז **אילו שדות נמשכים מ-Firestore** לזרימת החיזוי (`predict_injury_risk_from_firestore`), ו**אילו שמות עמודות קיימים במודל** (`injury_model.pkl`), כפי שמוגדרים בקוד.

**מקורות:**  
`backend/services/history_service.py` (`fetch_daily_firestore_snapshot`, `predict_injury_risk_from_firestore` דרך `prediction_service.py`),  
`backend/schemas/inference.py` (`InjuryPredictionRequest`),  
`backend/services/model_features.py` (`MODEL_FEATURE_COLUMNS`),  
`backend/docs/DATA_CONTRACT_FRONTEND_BACKEND.md` (contract באנגלית).

**תכנון פיצ’רים ופערים מול Firestore:** `[FEATURE_PLAN_FIRESTORE_HE.md](FEATURE_PLAN_FIRESTORE_HE.md)`.

---

## 1. מבנה המסמכים ב-Firestore (מה נטען ליום נתון)

לקריאת חיזוי יומי, הבקאנד טוען ארבעה מקורות:


| מסמך         | נתיב                                       |
| ------------ | ------------------------------------------ |
| פרופיל משתמש | `users/{uid}`                              |
| בריאות יומית | `users/{uid}/daily_health/{yyyy-MM-dd}`    |
| צ׳ק-אין יומי | `users/{uid}/daily_checkins/{yyyy-MM-dd}`  |
| תזונה יומית  | `users/{uid}/daily_nutrition/{yyyy-MM-dd}` |


בנוסף, לחישוב מאפיינים רולינג (7 ימים), הבקאנד קורא היסטוריה מ־`daily_health` ו־`daily_checkins` בתוך חלון התאריכים הרלוונטי — ראו `fetch_user_history` ב־`history_service.py`.

---

## 2. טבלת שדות: Firestore → בקשה פנימית → תפקיד במודל

העמודה **בקשה פנימית** היא שם השדה ב־`InjuryPredictionRequest` (camelCase). המודל עצמו עובד בשמות **snake_case** אחרי הנדסת פיצ’רים.


| מקור Firestore    | שם שדה ב-Firestore                             | שם בבקשה הפנימית               | שימוש עיקרי במודל / הערות                            |
| ----------------- | ---------------------------------------------- | ------------------------------ | ---------------------------------------------------- |
| `users/{uid}`     | `age`                                          | `age`                          | `age`                                                |
| `users/{uid}`     | `historyInjuryCount` או `history_injury_count` | `history_injury_count` (alias) | `history_injury_count`                               |
| `daily_health`    | `sleepMinutes`                                 | `sleepMinutes`                 | `sleep_hours`, אותות התאוששות                        |
| `daily_health`    | `steps`                                        | `steps`                        | `daily_distance_km` (גיבוי), `avg_cadence`, עומס     |
| `daily_health`    | `distanceMeters`                               | `distanceMeters`               | `daily_distance_km` (עיקרי), עומס                    |
| `daily_health`    | `activeCalories`                               | `activeCalories`               | `workout_intensity_minutes`, עומס חריף               |
| `daily_health`    | `totalCalories`                                | `totalCalories`                | `total_calories_burned` (שריפה)                      |
| `daily_health`    | `heartRateAvg`                                 | `heartRateAvg`                 | `resting_hr`, פרוקסי ל־`hrv_score`                   |
| `daily_health`    | `heartRateMax`                                 | `heartRateMax`                 | נספח בבקשה; לא נכנס ישירות לוקטור המודל כעמודה נפרדת |
| `daily_health`    | `heartRateMin`                                 | `heartRateMin`                 | מסייע ל־`resting_hr`                                 |
| `daily_health`    | `weightKg`                                     | `weightKg`                     | `bmi` (בקוד: הנחת גובה קבועה לחישוב)                 |
| `daily_health`    | `bmrCalories`                                  | `bmrCalories`                  | שריפת קלוריות / איזון קלורי                          |
| `daily_checkins`  | `energyLevel`                                  | `energyLevel`                  | `energy_level` (קנה מידה 1–10)                      |
| `daily_checkins`  | `muscleSoreness`                               | `muscleSoreness`               | `muscle_soreness` (קנה מידה 1–10)                    |
| `daily_checkins`  | `stressLevel`                                  | `stressLevel`                  | `stress_level` (קנה מידה 1–10)                       |
| `daily_nutrition` | `totalCalories`                                | `nutritionTotalCalories`       | `nutrition_intake_calories` (צריכת קלוריות מארוחות)  |
| `daily_nutrition` | `totalProtein`                                 | `totalProtein`                 | גזירת `daily_calories` (מאקרו)                       |
| `daily_nutrition` | `totalCarbs`                                   | `totalCarbs`                   | גזירת `daily_calories` (מאקרו)                       |
| `daily_nutrition` | `mealsLoggedCount`                             | `mealsLoggedCount`             | גזירת `daily_calories` כשיש ארוחות                   |


**מזהים לוגיים:** הבקאנד מוסיף לבקשה גם `userId` ו־`date` (לא מגיעים ממסמך Firestore אלא מהטריגר ל־API).

### 2.1 חלבון ושאר נתוני התזונה

**מה באמת נשמר ב-Firestore (אפליקציה):** לכל יום, תחת `users/{uid}/daily_nutrition/{yyyy-MM-dd}` נשמרים:

- **מסמך היום (אגרגציה):** בין השאר `totalProtein`, `totalCarbs`, `totalCalories` (סכום קלוריות מהארוחות), `mealsLoggedCount`, `lastMealAddedAt` — עדכון ב־merge כשמוסיפים ארוחה.
- **תת־אוסף `meals`:** לכל ארוחה מסמך עם שדות כמו `calories`, `protein`, `carbs`, `timestamp` (ראו `MealAnalysisActivity.kt`).

כלומר **כן** — נתונים מפורטים per-meal נשמרים; השם ב-Firestore הוא תת־מסמכים תחת `daily_nutrition/.../meals`, לא רק שלושה שדות סיכום.

**מה הבקאנד טוען לחיזוי:** `fetch_daily_firestore_snapshot` קורא רק את **מסמך יום התזונה** (`nutrition_doc.to_dict()`), **לא** את תת־האוסף `meals`. בבניית `InjuryPredictionRequest` ממופים `totalProtein`, `totalCarbs`, `mealsLoggedCount` וגם `totalCalories` (דרך `nutritionTotalCalories`). במודל אין עמודות נפרדות לחלבון/פחמימות; הן משמשות לגזירת `daily_calories`, ו־`totalCalories` של התזונה ממופה ל־`nutrition_intake_calories`. שימו לב: `totalCalories` ב־`daily_health` הוא שריפה (burn), ואילו `totalCalories` ב־`daily_nutrition` הוא צריכה (intake).

בסכימת ה-API `**אין**` שדות תזונה נוספים מעבר לשלושה הנ״ל (אין שומן, סיבים וכו’ ב־`InjuryPredictionRequest`).

**איך מחשבים צריכה יומית (`daily_calories`)** ב־`injury_request_to_model_dataframe` (`preprocessing.py`):

1. אנרגיה ממאקרו: (\text{חלבון} + \text{פחמימות}) \times 4 קלוריות לגרם (שומן לא מוזן — מוסיפים מקדם **×1.2** על סך האנרגיה מהמאקרו כהערכת שומן חסר).
2. אם אין מאקרו אבל `mealsLoggedCount > 0` — משתמשים בברירת מחדל של צריכה (`DEFAULT_FEATURE_VALUES`) עם מתיחה לפי מספר ארוחות.
3. אם אין לא מאקרו ולא ארוחות רלוונטיות — נופלים לברירת המחדל הקבועה לצריכה (כרגע 2500).

**איכות קלט:** `totalProtein`, `totalCarbs`, `mealsLoggedCount` מוגדרים כ־**שדות סובלניים** (`TOLERANT_FIELDS`) — חוסר בהם **לא** מוריד את ציון איכות הקלט (בניגוד לשדות רגישים כמו שינה וצעדים).

---

## 3. שדות שנכתבים חזרה ל-Firestore אחרי חיזוי מוצלח

ב־`save_daily_prediction_result` התוצאות נשמרות ב־**merge** תחת:

`users/{uid}/daily_health/{yyyy-MM-dd}`


| שדה ב-Firestore       | משמעות                                   |
| --------------------- | ---------------------------------------- |
| `finalRiskScore`      | ציון סיכון 0–100 (מהסתברות המודל × 100)  |
| `riskLevel`           | רמת סיכון טקסטואלית מהשרת                |
| `predictionConfidence`| בטחון חיזוי 0–100                         |
| `predictionUpdatedAt` | חותמת זמן ISO                            |

### 3.1 שדות קיימים במסמך שלא משמשים כקלט מודל באותו יום

ב־`daily_health/{date}` יש שדות שמייצגים תוצאת חיזוי/תצוגה (`finalRiskScore`, `riskLevel`, `predictionConfidence`, `predictionUpdatedAt`, `aiRecommendation`) והשרת לא משתמש בהם כקלט ל־feature vector של אותו יום.  
כקלט נלקחים אותות בריאות גולמיים (`sleepMinutes`, `steps`, `distanceMeters`, `activeCalories`, `totalCalories`, `heartRate*`, `weightKg`, `bmrCalories`, `injuredYesterday`) יחד עם check-in ותזונה.


---

## 4. רשימת עמודות המודל (וקטור הפיצ’רים)

החוזה הקבוע לשרת מוגדר ב־`MODEL_FEATURE_COLUMNS` ב־`backend/services/model_features.py`. זהו סדר העמודות של שורת הפיצ’רים לפני תאימות ל־`feature_columns` שנשמרו ב־pickle.

### 4.1 כל 26 העמודות (`MODEL_FEATURE_COLUMNS`)

סדר זהה ל־`backend/services/model_features.py` (לפני subset של המאמן השמור ב־bundle).


| #   | עמודת מודל (snake_case)      | מקור טיפוסי                                                              |
| --- | ---------------------------- | ------------------------------------------------------------------------ |
| 1   | `bmi`                        | מ־`weightKg` + הנחת גובה, או ברירת מחדל                                  |
| 2   | `age`                        | פרופיל / ברירת מחדל                                                      |
| 3   | `history_injury_count`       | פרופיל / ברירת מחדל                                                      |
| 4   | `injured_yesterday`          | `daily_health` היום — `injuredYesterday` (פציעה ביום הקודם)               |
| 5   | `daily_distance_km`        | `distanceMeters` / `steps`                                               |
| 6   | `workout_intensity_minutes`  | מרחק + `activeCalories`                                                  |
| 7   | `avg_cadence`                | מ־`steps` ומרחק                                                          |
| 8   | `sleep_hours`                | מ־`sleepMinutes`                                                         |
| 9   | `hrv_score`                  | פרוקסי מ־דופק מנוחה                                                      |
| 10  | `resting_hr`                 | `heartRateMin` / `heartRateAvg`                                           |
| 11  | `nutrition_intake_calories`  | נגזר מתזונה (`totalCalories` במסמך תזונה אם קיים) או ברירת מחדל           |
| 12  | `daily_calories`             | מאקרו / ארוחות / ברירות מחדל                                             |
| 13  | `total_calories_burned`      | `totalCalories` ב־`daily_health`, BMR, פעילות                             |
| 14  | `stress_level`               | `stressLevel` (קנה מידה 1–10)                                            |
| 15  | `muscle_soreness`            | `muscleSoreness` (קנה מידה 1–10)                                           |
| 16  | `energy_level`               | `energyLevel` בצ׳ק־אין (קנה מידה 1–10)                                   |
| 17  | `acute_load_7d`              | פרוקסי יום בודד או חישוב מהיסטוריה                                       |
| 18  | `chronic_load_21d`           | כנ״ל                                                                     |
| 19  | `acwr_ratio`                 | כנ״ל                                                                     |
| 20  | `acwr_ratio_ma7`             | התאמה ליום בודד או עדכון מהיסטוריה                                       |
| 21  | `acwr_ratio_std21`           | נגזר מ־ACWR/HRV בפריסה חד־יומית                                           |
| 22  | `calorie_balance`            | `daily_calories` − `total_calories_burned`                               |
| 23  | `sleep_hours_ma7`            | התאמה ליום בודד או עדכון מהיסטוריה                                       |
| 24  | `sleep_hours_std21`          | נגזר משינה בפריסה חד־יומית                                                |
| 25  | `sleep_debt_3d`              | פרוקסי או גלילה מהיסטוריה                                                |
| 26  | `hrv_drop`                   | פרוקסי או גלילה מהיסטוריה                                                |


### 4.2 subset אחרי אימון

קובץ `injury_model.pkl` עשוי להכיל רשימת `feature_columns` **קצרה יותר** אחרי בחירת מאפיינים באימון. בזמן ריצה, המודל משתמש **רק בעמודות שמופיעות ב־bundle** — ראו `validate_feature_vector_for_model` ו־`_resolve_model_bundle` ב־`prediction_service.py`.

---

## 5. סיכום מהיר

- **מ-Firestore נטענים** שדות הפרופיל (`age`, `historyInjuryCount`/`history_injury_count`), שדות הבריאות היומיים, צ׳ק-אין, ותזונה — לפי המיפוי בטבלה בסעיף 2.  
  **תזונה:** `totalProtein` / `totalCarbs` / `mealsLoggedCount` / `totalCalories` (intake), עם גזירה ל־`daily_calories` ו־`calorie_balance`.
- **במודל (וקטור מלא)** 26 עמודות ב־`MODEL_FEATURE_COLUMNS`; חלקן נגזרות בקוד מצירוף השדות הנ״ל, וחלקן (עומס רולינג, חוב שינה, ירידת HRV) עשויות להתעדכן מ**היסטוריית** `daily_health`/`daily_checkins` כשקיימים מספיק ימים.
- **חוזה מפורט באנגלית** (כולל מינימום שדות יומי מומלץ): `backend/docs/DATA_CONTRACT_FRONTEND_BACKEND.md`.

