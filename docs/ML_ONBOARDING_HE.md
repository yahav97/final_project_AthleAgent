# AthleAgent — מדריך חפיפה למפתח חדש (Machine Learning)

מסמך זה מרכז את כל מה שמפתח חדש צריך לדעת על תחום ה־ML בפרויקט: איך הדאטה נוצר, איך מאמנים מודל, איך מחליטים מה "מודל חי", ומה קורה בזמן אינפרנס בבקאנד.

---

## 1. מטרת שכבת ה־ML במוצר

שכבת ה־ML מספקת הערכת **סיכון לפציעה ביום הבא** על בסיס נתוני עומס, התאוששות, סטרס ותזונה.

בפועל:
- הטריגר היומי המומלץ הוא `POST /predict/daily` עם `userId+date` בלבד.
- הבקאנד מושך עצמאית מ-Firestore את נתוני היום והפרופיל, ומבצע enrichment היסטורי.
- לחלופין (advanced/compat): ניתן עדיין לשלוח payload מלא דרך `POST /predict`.
- payload עובר מיפוי/ניקוי/הנדסת פיצ'רים.
- המודל מחזיר הסתברות `risk_score` בטווח `0..1`.
- לפי ספי החלטה מה־artifact נקבע `risk_level` (`Low/Medium/High`) והמלצה.

---

## 2. מבנה רכיבי ML בפרויקט

| רכיב | מיקום | אחריות |
|------|-------|--------|
| יצירת דאטה סינתטי | `ML_model/data_generator.py` | מייצר dataset כרונולוגי ברמת ספורטאי/יום + label `injury_tomorrow`. |
| יצירת holdout קבוע | `ML_model/create_benchmark_set.py` | יוצר קבוצת benchmark לפי חלוקה ברמת `athlete_id` לצורך השוואות יציבות. |
| אימון ובחירת מודל | `ML_model/train_model.py` | מאמן קטלוג מודלים, מבצע threshold sweep, בוחר winner, ושומר artifacts + manifest. |
| וולידציית מדדים | `ML_model/validate_metrics.py` | אוכף gates/יעדים ומחזיר קוד יציאה המשפיע על promotion. |
| Pipeline מלא + promotion | `ML_model/run_pipeline.py` | מריץ הכל סדרתית וכותב `artifacts/promoted.json`. |
| טעינת מודל בפרודקשן | `backend/ml/model_loader.py` | טוען מודל promoted ומאמת manifest לפני מצב Live. |
| אינפרנס בזמן אמת | `backend/services/prediction_service.py` | orchestration של preprocessing + model.predict_proba + response, כולל מסלול Firestore-first. |
| מיפוי payload לפיצ'רים | `backend/services/preprocessing.py` | normalization, imputation, quality score, validation. |
| חוזה פיצ'רים קבוע | `backend/services/model_features.py` | רשימת פיצ'רים וספריית default values. |
| נגזרות עומס/התאוששות | `backend/services/feature_engineering.py` + `history_service.py` | חישוב ACWR ודומים מ-snapshot/היסטוריה. |

---

## 3. דאטה סינתטי (ה"דאטה המומצא")

### 3.1 למה בכלל דאטה סינתטי?

בשלב זה הפרויקט משתמש בדאטה מיוצר כדי:
- לאפשר איטרציה מהירה על מודלים וחוזי serving.
- לייצר התנהגות ריאליסטית לאורך זמן (time-series per athlete).
- לבדוק מדדי בטיחות/סף עוד לפני שיש קורפוס אמיתי גדול.

### 3.2 איך הדאטה נוצר בפועל

הגנרטור (`data_generator.py`) מדמה:
- **1000 ספורטאים** כברירת מחדל.
- **365 ימים לספורטאי**.
- total ברירת מחדל ~`365,000` שורות לפני סינון NaN בגלגולים.

לכל ספורטאי מוגדר baseline אישי (גיל, BMI, VO2max, היסטוריית פציעות, HRV בסיסי וכו'), ובכל יום מחושבים:
- עומס: `daily_distance_km`, `workout_intensity_minutes`, cadence.
- התאוששות: `sleep_hours`, `hrv_score`, `resting_hr`.
- תזונה: `daily_calories`, `total_calories_burned`, `calorie_balance`.
- סובייקטיבי: `stress_level`, `muscle_soreness`.
- נגזרות זמן: `acute_load_7d`, `chronic_load_21d`, `acwr_ratio`, `sleep_debt_3d`, `hrv_drop`.

### 3.3 מנגנון ה-label

ה-label הוא `injury_tomorrow` ונבנה ממודל hazard לוגיסטי עם:
- תרומה חיובית ל־risk: ACWR גבוה, debt שינה, HRV drop, סטרס, היסטוריית פציעה.
- אינטראקציות (synergy) בין עומס לשינה.
- גורמי הגנה (recovery, resilience, VO2 גבוה).
- אפקטים דינמיים: cooldown אחרי אירוע פציעה.

בנוסף מוחדרים:
- **Hard negatives** (ספורטאי בסיכון גבוה שנשאר בריא).
- **Rare unexplained injuries** (רעש תוויות נמוך).

מטרה: לשמור דאטה פחות "נקי" ויותר קרוב למציאות תפעולית.

### 3.4 איכות dataset

הגנרטור כותב גם `dataset_quality_report.json` עם:
- שיעור פציעה, class counts.
- טווחי פיצ'רים קריטיים.
- שיעורי תנאי סיכון (למשל `acwr>1.4`).
- קורלציות בסיסיות בין פיצ'רים.

---

## 4. חוזה דאטה לאימון (מה נכנס למודל)

פיצ'רי המודל מוגדרים במפורש ב־`MODEL_FEATURE_COLUMNS` (`backend/services/model_features.py`):

- פרופיל: `age`, `bmi`, `history_injury_count`, `vo2_max`
- עומס/ביצועים: `daily_distance_km`, `workout_intensity_minutes`, `avg_cadence`
- התאוששות: `sleep_hours`, `hrv_score`, `resting_hr`
- תזונה: `daily_calories`, `total_calories_burned`, `calorie_balance`
- סובייקטיבי: `stress_level`, `muscle_soreness`
- time-series נגזרות: `acute_load_7d`, `chronic_load_21d`, `acwr_ratio`, `acwr_ratio_ma7`, `acwr_ratio_std21`, `sleep_hours_ma7`, `sleep_hours_std21`, `sleep_debt_3d`, `hrv_drop`

ה־label: `injury_tomorrow` (binary).

---

## 5. תהליך אימון ובחירת מודל

### 5.1 קטלוג מודלים נבחנים

`train_model.py` מאמן מספר מועמדים, כולל:
- Logistic Regression (עם scaling)
- RandomForest (כולל tuned)
- ExtraTrees (כולל tuned)
- GradientBoosting
- XGBoost (raw + calibrated variants)

### 5.2 שיטת split והערכה

- אם קיים `benchmark_holdout.csv`: חלוקה train/test לפי מזהי ספורטאים קבועים.
- אחרת: `GroupShuffleSplit` לפי `athlete_id` (מניעת leakage בין ימים של אותו ספורטאי).

### 5.3 מדדים שנשמרים

לכל מודל נשמרים בין היתר:
- `Recall@Threshold`, `Precision@Threshold`, `F1@Threshold`, `FPR@Threshold`
- `ROC-AUC`, `PR-AUC`
- `LogLoss`, `BrierScore`
- `BalancedAccuracy@Threshold`

### 5.4 Recall-first policy

הפרויקט מעדיף בטיחות (פחות פספוס פציעות) ולכן recall הוא תנאי מפתח:
- hard minimum: `Recall >= 0.85`
- target: `Recall >= 0.90`
- high target: `Recall >= 0.95`

בחירת winner מתבצעת לפי מיון שמעדיף:
1. `FPR` נמוך,
2. recall גבוה,
3. precision/F1 גבוהים,
4. AUC גבוה.

### 5.5 סף החלטה (threshold)

יש sweep אוטומטי על טווח ספים (`0.20..0.60`) לכל מודל.
הסף הזוכה נשמר במפורש ב־model bundle כ־`threshold`, ובנוסף `medium_threshold`.
ב-serving אין "מספר קסם" hardcoded: משתמשים בספים השמורים בארטיפקט.

---

## 6. ארטיפקטים, Manifest ו-Promotion

כל ריצת אימון כותבת תיקייה:
- `ML_model/artifacts/<run_id>/`

עם קבצים עיקריים:
- `injury_model.pkl` — bundle (estimator + metadata).
- `model_comparison.csv`
- `threshold_sweep.csv`
- `best_operating_points.csv`
- `calibration_curve_data.csv`
- `risk_bins_summary.csv`
- `feature_importance.csv` (אם נתמך למודל).
- `run_manifest.json`

`run_manifest.json` הוא מקור האמת התפעולי:
- מי המודל הזוכה (`winner`)
- סף הפעלה (`threshold`)
- policy
- winner metrics
- risk bins

`run_pipeline.py` מעדכן:
- `ML_model/artifacts/promoted.json`

שמצביע על ה-artifact הפעיל לשרת.

---

## 7. שערי איכות (Gates) לפני מודל Live

ב־`backend/ml/model_loader.py` יש gate validation לפני טעינה ל־Live:
- `Recall@Threshold >= 0.85` (hard gate)
- `ROC-AUC >= 0.60` (sanity gate ל-RC1)
- בדיקת תקינות manifest ושקובץ המודל קיים

אם gate נכשל:
- מצב מודל = `Blocked`
- `get_model()` מחזיר `None`
- `/predict` נכשל עם שגיאה (אין fallback prediction בנתיב production)

---

## 8. Serving בפרודקשן — מה מתקבל ומה יוצא

### 8.1 קלט API (Production First: `POST /predict/daily`)

נתיב הייצור המומלץ:
- קלט מינימלי: `userId`, `date`.
- הבקאנד שולף ישירות:
  - `users/{uid}` (פרופיל)
  - `users/{uid}/daily_health/{date}`
  - `users/{uid}/daily_checkins/{date}`
  - `users/{uid}/daily_nutrition/{date}`

נתיב תאימות/מתקדם:
- `POST /predict` עם `InjuryPredictionRequest` מלא.

### 8.2 קלט API מלא (`POST /predict`)

הסכמה מוגדרת ב־`backend/schemas/inference.py` (`InjuryPredictionRequest`):
- מזהים: `userId`, `date`
- פרופיל: `age`, `vo2Max/vo2_max`, `historyInjuryCount/history_injury_count`
- daily health: `sleepMinutes`, `steps`, `distanceMeters`, `activeCalories`, `totalCalories`, `heartRate*`, `weightKg`, `bmrCalories`
- daily check-in: `energyLevel`, `muscleSoreness`, `stressLevel`
- תזונה יומית: `totalProtein`, `totalCarbs`, `mealsLoggedCount`

כל השדות אופציונליים ברמת schema, אבל איכות המידע משפיעה ישירות על החיזוי.

### 8.3 שלבי עיבוד בבקאנד

1. **Mapping + normalization** (`preprocessing.py`)
   - המרות יחידות (למשל `sleepMinutes` ל־`sleep_hours`).
   - scale mapping (`stressLevel`, `muscleSoreness` לטווח אימון).
   - clipping לגבולות סבירים.

2. **Feature engineering** (`feature_engineering.py`)
   - חישוב proxy ל־ACWR, sleep debt, HRV drop כשיש snapshot בלבד.

3. **History-aware enrichment** (`history_service.py` + `prediction_service.py`)
   - מתבצע ניסיון להביא 7 ימי היסטוריה מ־Firestore מהימים הקודמים (ללא יום המטרה).
   - confidence לפי כמות ימים: high/medium/low.
   - כשחסרים אותות load/recovery ביום הנוכחי: נעשה backfill מהיום ההיסטורי האחרון הזמין.
   - כשאין היסטוריה מספקת: fallback לערכי baseline מתוך `DEFAULT_FEATURE_VALUES`.

4. **Data quality scoring**
   - hard fields (`userId`, `date`) + איתותי עומס/התאוששות מינימליים.
   - שדות sensitive חסרים מורידים ניקוד.
   - אם יש hard blockers או ציון נמוך מאוד (`<0.35`) → הבקשה נחסמת.

5. **Vector validation**
   - התאמה מדויקת לחוזה `feature_columns` מהמודל.
   - בדיקות NaN / finite / טווחים קריטיים.

6. **Inference**
   - `model.predict_proba(X)[0,1]`
   - mapping ל־Low/Medium/High לפי ספים מה־bundle.

### 8.4 פלט API (`InjuryPredictionResponse`)

השרת מחזיר:
- `risk_score` — הסתברות פציעה (`0..1`)
- `risk_level` — `Low | Medium | High`
- `recommendation` — טקסט פעולה כולל הערת confidence
- `data_quality_score` — `0..1`
- `data_quality_status` — `Excellent | Good | Fair | Poor`
- `meta`:
  - `model_version` (לרוב שם winner)
  - `fallback_reason` (`none` כשהמודל live)
  - `confidence_bucket` (`Low | Medium | High`)

בנוסף במסלול `POST /predict/daily`:
- תוצאת החיזוי נשמרת אוטומטית ב־Firestore תחת `users/{uid}/daily_health/{date}` (merge), כולל score/level/recommendation/meta ושדות איכות.

---

## 9. מצב נוכחי (snapshot מה-artifact promoted)

לפי `ML_model/artifacts/promoted.json`:
- promoted run: `20260430_142014`
- `degraded_rc: true`

לפי manifest של run זה:
- winner: `ExtraTrees`
- threshold: `0.36`
- Recall@Threshold: `0.9696` (עובר hard gate)
- ROC-AUC: `0.6400` (עובר gate של 0.60)
- Precision/F1 נמוכים יחסית (צפוי במדיניות recall-first)

כלומר המודל תקין ל-Live לפי gates, אך יש מחיר תפעולי של הרבה false positives (FPR גבוה).

---

## 10. הבדל בין `/demo_predict` ל־`/predict`

חשוב לחפיפה:
- `POST /demo_predict` ב־`api/routes/predict.py` הוא heuristic endpoint פשוט ללקוחות legacy/demo.
- `POST /predict` הוא נתיב הייצור ה"אמיתי" של שכבת ה־ML, עם quality gates, model gates, היסטוריה ו-manifest governance.

לשינויים ב־ML ותיקוף מוצר, יש להתייחס ל־`/predict` כמקור האמת.

בנוסף:
- `POST /predict/daily` הוא נתיב הטריגר המומלץ למוצר (Firestore-first).
- `POST /predict` נשאר כנתיב מתקדם למקרה שבו רוצים להזין payload מלא ידנית.

---

## 11. תהליך עבודה מומלץ למפתח ML חדש

1. להריץ pipeline מקצה לקצה:
   - `python ML_model/run_pipeline.py`
2. לבדוק artifacts ו־`run_manifest.json`.
3. לאמת ש־`promoted.json` מצביע לריצה הרצויה.
4. להרים backend ולבדוק:
   - `GET /status/ml` שהמצב `Live`.
   - `POST /predict` עם payloadים במצבי data איכות שונים.
5. לפני שינוי פיצ'רים:
   - לעדכן גם `MODEL_FEATURE_COLUMNS` וגם preprocessing/serving parity.
6. לשמור תאימות בין train ל-serve:
   - כל feature חדש באימון חייב דרך בנייה מוגדרת גם בזמן אינפרנס.

---

## 12. נקודות תשומת לב (Risk & Debt)

- **פער domain בין synthetic ל-real world:** המדדים כרגע אמיתיים יחסית, אבל הלייבל נובע מסימולציה.
- **Precision/FPR tradeoff:** policy מוטה recall; כדאי להגדיר ספי התערבות מוצריים בהתאם.
- **Proxy features ב-serving:** חלק מהפיצ'רים מחושבים מקורב כשאין היסטוריה מלאה.
- **תלות ב־Firestore history:** ללא היסטוריה איכות confidence יורד ונכנסים defaults.
- **ניהול גרסאות:** manifest + promoted הם קריטיים; שינוי ידני לא מבוקר עלול לשבור Live.

---

## 13. קבצים מרכזיים לקריאה ראשונה

| נושא | קובץ |
|------|------|
| גנרציית דאטה ולייבל | `ML_model/data_generator.py` |
| אימון, בחירה, threshold | `ML_model/train_model.py` |
| ולידציית מדדים | `ML_model/validate_metrics.py` |
| pipeline + promotion | `ML_model/run_pipeline.py` |
| טעינת מודל ו-gates | `backend/ml/model_loader.py` |
| preprocessing ל-serving | `backend/services/preprocessing.py` |
| orchestration אינפרנס | `backend/services/prediction_service.py` |
| חוזה פיצ'רים קבוע | `backend/services/model_features.py` |

---

מסמך זה משקף את מצב הקוד הנוכחי. בכל שינוי ב-feature contract, policy, או thresholding — יש לעדכן את המסמך יחד עם הקוד כדי לשמור חפיפה מדויקת למפתחים חדשים.
