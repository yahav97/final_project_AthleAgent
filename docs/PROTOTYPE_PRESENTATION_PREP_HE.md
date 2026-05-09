# הכנה להצגת פרוטוטייפ — AthleAgent

מסמך הכנה אישי לקראת הצגת הפרוטוטייפ למרצה. את על הבקאנד+המודל, השותף על הפרונט. בדמו עצמו נשתמש ב־`/demo_predict` (היוריסטיקה פשוטה) ולא במודל הייצור (`/predict/daily` עם ExtraTrees) — חשוב שתדעי **למה** ותוכלי להגן על ההחלטה הזאת.

---

## 0. ארבעת המשפטים שאת חייבת לדקלם בעל פה

1. **מה האפליקציה עושה:** "AthleAgent מאחדת נתונים סובייקטיביים (שאלון יומי), נתונים אובייקטיביים מ־Health Connect (שינה, צעדים, דופק), וניתוח תזונה בעזרת Gemini Vision, ומחזירה ציון סיכון יומי לפציעה לספורטאי, עם תצוגה גם למאמן."
2. **איך הציון נוצר:** "ציון הסיכון מתקבל מהבקאנד (FastAPI). קיים נתיב ייצור (`POST /predict/daily`) שמריץ מודל ExtraTrees מאומן על דאטה סינתטי של 1,000 ספורטאים × 365 ימים. בנוסף יש נתיב הדגמה (`/demo_predict`) שמחשב ציון היוריסטי דטרמיניסטי — וזה מה שאנחנו מציגים בדמו כדי לקבל תוצאה צפויה ויציבה ללא תלות בהיסטוריה."
3. **תפקיד החלוקה ביננו:** "השותף שלי בנה את האפליקציה ב־Kotlin/Android, אני בניתי את שכבת השרת, צינור ה־ML והמיפוי בין נתוני Firestore לפיצ'רים של המודל."
4. **המצב:** "MVP עובד מקצה־לקצה: Auth → איסוף נתונים → Firestore → Backend → ציון → UI. המודל הוא RC1 על דאטה סינתטי; המעבר לדאטה אמיתי הוא השלב הבא."

---

## 1. מבנה ההצגה המוצע (15 דקות)

| דק' | מה מציגים | מי מציג |
|----|-----------|---------|
| 0–2 | בעיה ומטרה: מעבר מטיפול תגובתי למניעתי בפציעות ספורטאים | את + שותף |
| 2–5 | סיור באפליקציה: Login → Home Athlete → Check-in → Wearable Sync → Meal → Dashboard → Coach view | שותף |
| 5–8 | הארכיטקטורה: Android ↔ Firebase ↔ FastAPI; מה זורם איפה | את |
| 8–12 | המודל: דאטה, פיצ'רים, איך בחרנו winner, איך נראה Recall vs Precision, ולמה הדמו רץ ב־`/demo_predict` | את |
| 12–14 | מה עובד / מה נשאר / תוכנית להמשך | את + שותף |
| 14–15 | שאלות | — |

---

## 2. הצד שאת חייבת להכיר — הפרונט (Android)

זה לא הצד שלך, אבל את חייבת לדעת לתת תשובת חירום אם המרצה ישאל אותך ישירות.

### 2.1 סטאק
- **Kotlin + Android SDK + Material**, ארכיטקטורת **MVVM**.
- **Firebase Auth** (כולל Google דרך FirebaseUI) — אימות + ניהול משתמשים.
- **Cloud Firestore** — מסד נתוני המוצר (פרופיל, נתוני יום, קבוצה).
- **Health Connect** — מקור הנתונים האובייקטיביים מהמכשיר/שעון.
- **Gemini Vision API** — ניתוח תמונת ארוחה לערכים תזונתיים.
- **Retrofit** — קריאות HTTP לבקאנד FastAPI.
- **MPAndroidChart** — גרף היסטורי של 7 הימים האחרונים.

### 2.2 המסכים והזרימות

נקודת הכניסה ב־`AndroidManifest` היא `LoginActivity`. אחרי התחברות, `MainActivity` בודק את ה־`role` ב־Firestore ומנתב לזרימת ספורטאי או מאמן.

**זרימת ספורטאי:**

| מסך | קובץ | מה הוא עושה |
|-----|------|-------------|
| התחברות | `LoginActivity` + `LoginManager` | Firebase Auth (Google), יצירת/טעינת פרופיל ב־Firestore, ניתוב לפי role |
| בית ספורטאי | `HomeAthleteActivity` | 4 כפתורים ראשיים + התראות (`AlertItem`) על מה חסר היום: Wearable Sync / Check-in / Meal |
| צ'ק־אין יומי | `DailyCheckInActivity` | שאלון: כאב שרירים (1–5), אנרגיה (slider), סטרס (slider) → נכתב ל־`users/{uid}/daily_checkins/{date}` |
| סנכרון Wearable | `WearableSyncActivity` | Health Connect: שינה, צעדים, מרחק, קלוריות פעילות/כולל, דופק (avg/max/min), משקל, BMR → `users/{uid}/daily_health/{date}` |
| תזונה | `HomeAthleteActivity` → `AnalyzingMealActivity` → `MealAnalysisActivity` | תמונה (מצלמה/גלריה) → Gemini Vision מחזיר JSON עם calories/protein/carbs → תצוגה ושמירה ב־`daily_nutrition` |
| דשבורד סיכון | `AthleteDashboardActivity` | טוען `daily_health` + `daily_checkins` של היום, שולח לבקאנד, מציג ציון בצבע (ירוק/צהוב/כתום/אדום), המלצת AI מ־Gemini, וגרף 7 ימים |
| הצטרפות לקבוצה | `JoinTeamActivity` | יוצר בקשת join לקבוצה ב־Firestore |

**זרימת מאמן:**

| מסך | קובץ | מה הוא עושה |
|-----|------|-------------|
| בית מאמן | `HomeCoachActivity` | שם הקבוצה, התראות על בקשות ממתינות |
| בקשות | `CoachRequestsActivity` | אישור/דחייה של בקשות ספורטאים |
| דשבורד מאמן | `CoachDashboardActivity` | רשימת ספורטאי הקבוצה; בלחיצה על ספורטאי — `finalRiskScore`, ההמלצה האחרונה, וגרף 7 ימים |

### 2.3 איך הפרונט מתחבר לבקאנד שלי

- `network/ApiClient.kt` — Retrofit עם `BASE_URL = http://10.0.2.2:8000/` (alias של אמולטור ל־localhost של המחשב המארח). במכשיר פיזי צריך IP מקומי.
- `network/ApiService.kt` — מגדיר `POST /demo_predict` עם `data class AthleteData` (20 שדות).
- `AthleteDashboardActivity.fetchDataAndSendToBackend()` — שואב מ־Firestore את `sleepMinutes`, `steps`, `muscleSoreness`, `stressLevel` של היום, בונה payload (חלק מהשדות עם ערכי default קשיחים: גיל=25, BMI=22.5, VO2Max=50…) ושולח ל־`/demo_predict`.
- התשובה מכילה `risk_percentage` ו־`risk_level` → מציגים אחוז ב־ProgressBar צבעוני, שומרים `finalRiskScore` ב־`daily_health/{today}`, ואז שולחים את הציון ל־Gemini Text כדי לקבל המלצה במשפט.

### 2.4 שאלות שאת עלולה לקבל על הפרונט (תשובות מוכנות)

- **"איך מחזיקים מצב התחברות?"** — Firebase Auth שומר טוקן באופן מקומי; `MainActivity` בודק `currentUser` ומנתב לפי `role` ב־Firestore.
- **"מה קורה אם אין נתוני היום?"** — `HomeAthleteActivity.checkDailyDataStatus()` מציג כרטיסי התראה ("Missing Wearable Sync", "Missing Check-in", "Missing Meal Analysis") עם כפתור ישיר למסך הרלוונטי.
- **"למה Gemini ולא מודל פנימי לתזונה?"** — Gemini Vision מסיר את הצורך לאמן מודל זיהוי מנות; הוא מחזיר JSON מוגדר היטב, וזה סיפור MVP יעיל.
- **"איך הפרדתם בין ספורטאי למאמן?"** — שדה `role` ב־`users/{uid}` ב־Firestore + `MainActivity` שמנתב.

---

## 3. הצד שלך — בקאנד והמודל

### 3.1 הסטאק שלך (לדקלם בעל פה)

- **FastAPI** (Python) — שירות ה־HTTP.
- **scikit-learn** + **XGBoost** — קטלוג מודלים שנבחנו.
- **pandas / numpy** — הנדסת פיצ'רים ועיבוד.
- **firebase-admin** — קריאת/כתיבה ל־Firestore.
- **uvicorn** — שרת ASGI.
- ארכיטקטורה ברורה: `api/routes` → `services` → `ml/model_loader` → artifact מהצינור (`ML_model/artifacts/<run_id>/`).

### 3.2 הנתיבים בבקאנד (חייבת לדעת בעל פה)

| נתיב | מצב | למה הוא קיים |
|------|-----|-------------|
| `GET /` , `GET /health` | חי | health checks |
| `POST /test_predict` | mock | בדיקת UI ללא תלות במודל |
| `POST /demo_predict` | **בשימוש בפרונט עכשיו** | היוריסטיקה דטרמיניסטית: שינה, סטרס, soreness, ריצה. מחזיר `risk_percentage` |
| `POST /predict/daily` | **נתיב הייצור המומלץ** | טריגר מינימלי (`userId+date`); הבקאנד שולף לבד את כל נתוני היום מ־Firestore |
| `POST /predict` | אינפרנס מתקדם | payload מלא מהקליינט, נשמר לתאימות/דיבוג |
| `POST /predict/sklearn` | מנוטרל ב־default | endpoint legacy, מחזיר 410 |
| `GET /status/ml` | מטא־דאטה | סטטוס מודל (Live/Blocked), gate reasons |

### 3.3 איך נראה המסלול המלא של חיזוי ייצור (מה תגידי כשתשרטטי על הלוח)

```
Android (AthleteDashboard)
   │  POST /predict/daily  { userId, date }
   ▼
FastAPI route: predict_injury_daily
   │
   ├─ fetch_daily_firestore_snapshot(uid, date)
   │     שואב: profile + daily_health + daily_checkins + daily_nutrition
   │
   ├─ injury_request_to_model_dataframe(payload)   # mapping + normalization
   ├─ _backfill_today_row_from_recent_history()    # אם חסרים אותות עומס/התאוששות
   ├─ _apply_history_confidence_fallback()         # 7 ימי היסטוריה → ACWR, sleep_debt, etc.
   ├─ calculate_data_quality_score()               # ציון איכות 0..1 + hard blockers
   ├─ get_model() (ML_model/artifacts/promoted)
   ├─ validate_feature_vector_for_model()
   ├─ model.predict_proba(X)[0,1]                  # ExtraTrees
   ├─ risk_level לפי threshold מהארטיפקט (0.36)
   │
   ├─ persist_prediction_result_or_raise()         # שומר חזרה ל-Firestore daily_health
   └─ return InjuryPredictionResponse
```

הפרונט מקבל בחזרה:
- `risk_score` (0..1)
- `risk_level` (Low/Medium/High)
- `recommendation` (טקסט עם הערת confidence)
- `data_quality_score` + `data_quality_status`
- `meta`: `model_version`, `fallback_reason`, `confidence_bucket`

### 3.4 הדאטה הסינתטי — חייב להגיד עליו את האמת

- 1,000 ספורטאים × 365 ימים → ~365,000 שורות (`ML_model/data_generator.py`).
- כל ספורטאי עם baseline אישי (גיל, BMI, VO2max, היסטוריית פציעות).
- הדאטה כולל: עומס יומי (`daily_distance_km`, `workout_intensity_minutes`), התאוששות (`sleep_hours`, `hrv_score`, `resting_hr`), תזונה (`calorie_balance`), סובייקטיבי (`stress_level`, `muscle_soreness`), ונגזרות זמן (`acute_load_7d`, `chronic_load_21d`, `acwr_ratio`, `sleep_debt_3d`, `hrv_drop`).
- ה־**label** הוא `injury_tomorrow`, נבנה ממודל hazard לוגיסטי עם:
  - גורמי סיכון: ACWR גבוה, חוב שינה, ירידת HRV, סטרס, היסטוריית פציעות.
  - גורמי הגנה: VO2max גבוה, התאוששות טובה.
  - אינטראקציות (synergy) בין עומס לשינה.
  - **Hard negatives** (ספורטאי בסיכון גבוה שנשאר בריא) ו־**rare unexplained injuries** — כדי שהדאטה לא יהיה "נקי מדי".

### 3.5 הפיצ'רים שהמודל מקבל (מ־`MODEL_FEATURE_COLUMNS`)

- **פרופיל:** `age`, `bmi`, `history_injury_count`, `vo2_max`
- **עומס/ביצוע:** `daily_distance_km`, `workout_intensity_minutes`, `avg_cadence`
- **התאוששות:** `sleep_hours`, `hrv_score`, `resting_hr`
- **תזונה:** `daily_calories`, `total_calories_burned`, `calorie_balance`
- **סובייקטיבי:** `stress_level`, `muscle_soreness`
- **נגזרות זמן:** `acute_load_7d`, `chronic_load_21d`, `acwr_ratio`, `acwr_ratio_ma7`, `acwr_ratio_std21`, `sleep_hours_ma7`, `sleep_hours_std21`, `sleep_debt_3d`, `hrv_drop`

### 3.6 איך אומנה גרסת הייצור

- `train_model.py` מאמן קטלוג: Logistic Regression, RandomForest (גם tuned), ExtraTrees (גם tuned), GradientBoosting, XGBoost (raw + calibrated).
- **Split** עם `GroupShuffleSplit` לפי `athlete_id` כדי למנוע leakage בין ימים של אותו ספורטאי, או `benchmark_holdout.csv` קבוע.
- **Threshold sweep** אוטומטי בטווח 0.20..0.60 לכל מודל; הסף הזוכה נשמר ב־bundle.
- **בחירת winner** לפי policy "recall-first": קודם FPR נמוך, אחר כך recall גבוה, אחר כך precision/F1, אחר כך AUC.
- Gates לפני Live: `Recall@Threshold ≥ 0.85`, `ROC-AUC ≥ 0.60`, manifest תקין; אחרת המודל `Blocked`.

---

## 4. המודל בייצור עכשיו (RC1) — מספרים שאת חייבת לדעת

מהארטיפקט הנוכחי `ML_model/artifacts/20260430_142014/run_manifest.json`:

| מדד | ערך | משמעות |
|-----|-----|--------|
| **Winner** | `ExtraTrees` | אנסמבל של עצים אקראיים מאוד; פחות overfit מ־RF טהור |
| **Threshold** | `0.36` | סף ההחלטה שנבחר אוטומטית מה־sweep |
| **Recall@Threshold** | `0.97` | תופסים 97% מהפציעות בפועל |
| **Precision@Threshold** | `0.14` | רק 14% מהאזעקות הן באמת אירוע פציעה |
| **F1@Threshold** | `0.25` | נמוך — תוצאה ישירה של Precision נמוך |
| **FPR@Threshold** | `0.93` | 93% מהבריאים נצבעים בטעות כסיכון — הבעיה התפעולית הראשית |
| **ROC-AUC** | `0.64` | מעל הגייט אבל לא מצוין; מרחב הפרדה בינוני |
| **Brier Score** | `0.22` | קליברציה בינונית |

**Risk bins מהארטיפקט:**
- `yellow_20_50`: 46,785 דגימות, שיעור פציעה בפועל 10.4%
- `red_50_100`: 22,215 דגימות, שיעור פציעה בפועל 21.2%

מסקנה: יש הפרדה אמיתית בין צהוב לאדום (פי 2 בערך), אבל ה־Precision הנמוך והרבה false positives הם ה־debt העיקרי שאת מודה בו.

---

## 5. **למה מציגים עם `/demo_predict` ולא עם המודל האמיתי?**

זאת השאלה הכי חשובה — תכיני תשובה ברורה ובטוחה:

> "החלטה מודעת. הדמו צריך להיות **דטרמיניסטי וצפוי** מול המרצה: כל לחיצה תיתן ציון יציב על אותם נתונים, בלי תלות בהיסטוריה של 7 ימים בפרופיל אמיתי, בלי gate של איכות נתונים שיכול לחסום אותנו, ובלי ה־FPR הגבוה של ה־RC1 שיוביל לכל המקרים להיצבע 'High'. המודל האמיתי מחובר ועובד מאחורי `/predict/daily`, אבל לוגית הוא דורש שבעה ימי היסטוריה ב־Firestore ופרופיל אמיתי כדי להציג confidence סביר. מבחינת הצגה, ההיוריסטיקה ב־`/demo_predict` מספקת חוויה צפויה ויציבה ב־5 שניות, מה שמשרת את הדמו בצורה הטובה ביותר."

נימוקים נוספים שתוכלי לשלוף לפי הצורך:
1. **דטרמיניסטיות:** הציון תלוי רק ב־payload — מספר יציב מול מרצה.
2. **חוסר תלות ב־artifact:** אם משהו ב־`promoted.json` לא יעלה במחשב הדמו, ה־UI עדיין יעבוד.
3. **חוסר תלות בהיסטוריה:** המודל האמיתי "חי" טוב כשיש 7 ימי היסטוריה. בדמו על משתמש חדש זה ייכשל ב־`insufficient_input_quality` או יחזיר confidence נמוך.
4. **הדגשת הארכיטקטורה:** הדמו מציג שהקליינט→שרת→ציון עובד מקצה־לקצה. המודל האמיתי הוא רכיב פנימי שמוחלף בקלות בלי שינוי חוזה ה־API.
5. **שקיפות:** את לא מסתירה את המודל האמיתי — את מתכוונת לדבר עליו במפורש בחלק ה־ML.

---

## 6. אילו מדדים מעניינים אותך, ולמה (זה הלב של הצגת ה־ML)

### 6.1 הקדמה שצריך להגיד

> "בפרויקט בריאותי שעוסק במניעת פציעות, **לא כל המדדים שווים**. עלות של פציעה שלא נחזתה (false negative) גבוהה בהרבה מעלות של אזהרת שווא (false positive). לכן בנינו policy של **Recall-first**, וזה משפיע על איך שבחרנו winner ועל איך שאנחנו מודדים את ההצלחה."

### 6.2 המדדים — אחד אחד

| מדד | למה חשוב לי | מה הערך אצלי |
|-----|-------------|---------------|
| **Recall** (Sensitivity) | המדד הקריטי. Recall נמוך = פספסנו פציעה = ספורטאי מתאמן עם דגל אדום ולא יודע. הצבתי **hard gate של 0.85** ויעד 0.90, וריצת ה־RC1 עברה ב־0.97. | 0.97 |
| **Precision** | הסיפור התפעולי. Precision נמוך = הרבה התראות שווא → המאמן מתעלף מההתראות (alert fatigue). אצלי 0.14 — כן, נמוך, וזה מודע. | 0.14 |
| **FPR** | משלים ל־Precision מצד הסיווג. FPR=93% אומר ש־9 מתוך 10 ספורטאים בריאים מקבלים אזהרה. זה ה־**debt העיקרי** של RC1. | 0.93 |
| **F1** | אינדיקטור איזון. נמוך אצלי כי מאזן בין Recall גבוה ל־Precision נמוך — צפוי. | 0.25 |
| **ROC-AUC** | יכולת הפרדה ללא תלות בסף. 0.64 = "בינוני־סביר" — יש הפרדה אבל לא דרמטית. הצבתי כסף gate סנטריני 0.60. | 0.64 |
| **Brier / LogLoss** | קליברציה — האם ההסתברויות שהמודל מוציא אכן משקפות תדירות בפועל. | Brier 0.22 / LogLoss 0.64 |
| **Risk-bin injury rate** | המדד העסקי האמיתי. פי 2 הבדל בין yellow (10.4%) ל־red (21.2%) — הפרדה ממשית גם אם לא מושלמת. | 10.4% vs 21.2% |

### 6.3 איך מסבירים את ה־Precision הנמוך מול המרצה (טיעון אקדמי, לא התנצלות)

> "ה־Precision הנמוך הוא פועל יוצא **של מדיניות** ולא של חולשה במודל. ב־recall-first, הסף נדחף נמוך כדי לתפוס כמה שיותר אירועים. בעולם רפואי־ספורטיבי הציון לא משמש כ'מתריע אוטומטי' אלא כ**אינדיקטור לעיון של מאמן/רופא**, כך שעלות ה־false positive היא 'דקה של עיון נוסף', בעוד שעלות false negative היא פציעה. אם מחר נעבור למוצר עם התראות אוטומטיות, נעלה את הסף, נחליף ל־recall ≥ 0.90 בלבד עם precision גבוה משמעותית, ונשלם בהפסד recall — זה ידיר מודע."

### 6.4 הבחנה שתרשים את המרצה

המודל לא מחזיר רק ציון. הוא מחזיר גם:
- `data_quality_score` — אומר *כמה אפשר לסמוך* על הציון של היום.
- `confidence_bucket` — נגזר משילוב של איכות + היסטוריה.
- `recommendation` — טקסט שמתאים את ה־action לציון.

זה מציב את המודל כ־**decision support** ולא כ־**black-box classifier**, וזה ההבדל בין פרויקט סטודנטיאלי לבין מערכת שאפשר להתחיל לדבר על שילובה במציאות.

---

## 7. מה עובד / מה נשאר / מה נלמד

### 7.1 מה עובד (לדבר בביטחון)

- **Auth + ניתוב לפי role** — Firebase Auth + `MainActivity` עם branching לפי `role`.
- **איסוף נתונים מקצה לקצה:**
  - Health Connect → `daily_health`
  - שאלון יומי → `daily_checkins`
  - Gemini Vision → `daily_nutrition`
- **שתי זרימות UI מלאות:** ספורטאי (Home/Checkin/Sync/Meal/Dashboard) ומאמן (Home/Requests/Dashboard).
- **שני נתיבי חיזוי בבקאנד:** `/demo_predict` להצגה, `/predict/daily` לייצור.
- **צינור ML מלא:** generator → train → threshold sweep → manifest → promotion → gates → Live serving.
- **שמירה אוטומטית של הציון** ל־Firestore כדי שהמאמן יוכל לראות ציון של ספורטאי גם כשהוא לא מחובר עכשיו.
- **גרף 7 ימים** מבוסס Firestore (`finalRiskScore` כמסמכי יום).
- **Data quality gate** — הבקאנד חוסם תוצאה אם הקלט עני מדי (`insufficient_input_quality`), במקום להחזיר ציון מטעה.

### 7.2 מה לא עובד עדיין / debt מודע

- **Precision/FPR** של RC1 גבוהים מדי לסביבת ייצור אמיתית.
- **דאטה סינתטי** — הלייבל מסומלץ; יש domain gap מול דאטה אמיתי.
- **הפרונט עדיין קורא ל־`/demo_predict`** ולא ל־`/predict/daily` — מתועד במסמך מעבר נפרד (`docs/FRONTEND_PREDICTION_MIGRATION_HE.md`).
- **אין retry/idempotency policy מוגדרת** לקריאות חיזוי כפולות.
- **מסך מאמן** מציג את ה־`finalRiskScore` האחרון ולא ב־real-time push.
- **פרופיל קשיח בפרונט בדמו** — `age=25, bmi=22.5, vo2_max=50…` (ראי `AthleteDashboardActivity.fetchDataAndSendToBackend`); בייצור צריך לקרוא מ־`users/{uid}`.
- **אין ניטור production-grade** — יש לוגי קובץ אבל לא alerting ממוסד.

### 7.3 מה הצעדים הבאים (אחרי הצגה)

1. **מעבר הפרונט ל־`/predict/daily`** עם החוזה החדש (`risk_score 0..1`, חישוב אחוז בצד הקליינט).
2. **שיפור ה־Precision** — הוספת features (HRV variability, ניתוח sleep stages), כיול ספים שונים לאוכלוסיות שונות, calibration (Platt/Isotonic).
3. **מעבר לדאטה אמיתי** — אפילו 50–100 ספורטאים אמיתיים עם תיוג רטרוספקטיבי.
4. **A/B בין מודלים** — להוסיף XGBoost calibrated מול ExtraTrees ולהשוות גם על FPR.
5. **התראות למאמן** — push notification כשציון של ספורטאי קופץ מעל סף יומי.

---

## 8. שאלות מצופות מהמרצה — תשובות מוכנות

| שאלה | תשובה מומלצת |
|------|---------------|
| "למה לא הראיתם את המודל האמיתי בדמו?" | סעיף 5 — דטרמיניסטיות, חוסר תלות בהיסטוריה, יציבות הצגה. המודל **כן** רץ, מודגם ב־`/predict/daily`, ואני מציגה את המספרים שלו. |
| "למה Precision כל כך נמוך?" | סעיף 6.3 — תוצר של recall-first policy, מודע ומכוון. |
| "למה דאטה סינתטי?" | מאפשר איטרציה מהירה, יצירת hard negatives, וזרימה מקצה לקצה לפני קורפוס אמיתי. הדומיין הוא רגיש (פציעות → אישורים אתיים), ואנחנו פותחים את הדרך לדאטה אמיתי בהמשך. |
| "איך מנעתם data leakage?" | `GroupShuffleSplit` לפי `athlete_id` או `benchmark_holdout` קבוע — אף ספורטאי לא חוצה train/test. |
| "למה ExtraTrees ולא XGBoost?" | ExtraTrees ניצח על ה־policy שלנו (FPR-then-Recall ordering). XGBoost calibrated הגיע קרוב, אבל ExtraTrees נתן FPR טוב יותר באותו recall. |
| "למה לא Deep Learning?" | טבלאי + 24 פיצ'רים + ~345k שורות = ensemble of trees הם הבחירה הסטטיסטית הנכונה. DL ידרוש דאטה גדול בסדר גודל. |
| "מה קורה אם ה־API נופל?" | הפרונט מציג "Backend Connection Failed" (יש handler ב־`onFailure`). אין fallback אוטומטי לציון; זאת החלטה — אסור להציג ציון לא אמין. |
| "איך הציון נשמר?" | תוצאה תקינה נשמרת ע"י הבקאנד ב־`users/{uid}/daily_health/{date}` (merge), כולל `finalRiskScore`, `riskLevel`, `predictionMeta`, `predictionUpdatedAt`. |
| "איך תזונה משתלבת בציון?" | היום בעיקר אינפורמטיבית בדשבורד. בייצור הפיצ'רים `daily_calories`, `total_calories_burned`, `calorie_balance` מוזרמים למודל. |
| "איך אתם מטפלים בהרשאות בריאות?" | Health Connect דורש user grant מפורש לכל record type; יש מסך הסבר (`PrivacyPolicyActivity`) שמשמש גם כ־rationale. |
| "מה ההבדל בין `/demo_predict` ל־`/predict/daily`?" | `/demo_predict` = היוריסטיקה דטרמיניסטית, `/predict/daily` = מודל מאומן + Firestore-first + gates + persistence. |
| "מה זה ACWR?" | Acute:Chronic Workload Ratio — יחס בין עומס 7 ימים ל־21 ימים. ACWR מעל 1.3–1.5 מקושר בספרות לסיכון מוגבר לפציעה. זה אחד הפיצ'רים הכי משמעותיים אצלנו. |
| "מה היה אם היה לכם דאטה אמיתי?" | היינו צריכים לפחות 200–500 ספורטאים עם תיוגי פציעה מאומתים רטרוספקטיבית. בלי זה לא היינו יכולים לאמן בכלל. הסינתטי הוא **גשר**. |

---

## 9. הימנעי מהבורות האלה (חוויה מוכחת)

- **אל תגידי "המודל לא טוב"** — תגידי "ה־RC1 הנוכחי הוא תוצר של מדיניות recall-first, וזה debt מודע".
- **אל תמעיטי בערך הפרונט** — גם אם זה לא הצד שלך, הוא מציג עבודה רצינית של אינטגרציה (Health Connect, Gemini, Firebase).
- **אל תיכנסי לפרטי קוד מיותרים** — המרצה רוצה הבנה ארכיטקטונית, לא קריאת שורות.
- **אל תגידי "לא יודעת"** — אמרי "זה לא הצד שלי בפרויקט, השותף יכול להרחיב, אבל ברמת המערכת זה עובד כך…"
- **אל תפסחי על הסיבה לדמו** — היזמי את ההסבר; אם המרצה ישאל "למה לא המודל האמיתי?", זה כבר תגובתי.
- **אל תשכחי את הקרדיט המשותף** — "השותף בנה את הפרונט, אני בניתי את ה־ML pipeline ואת השרת, החוזים בינינו תועדו ב־`docs/FRONTEND_PREDICTION_MIGRATION_HE.md` ו־`docs/ML_ONBOARDING_HE.md`".

---

## 10. רשימת בדיקה לפני שאת נכנסת לכיתה

- [ ] הבקאנד רץ מקומית: `uvicorn main:app --reload --port 8000`.
- [ ] האמולטור (או מכשיר) פתוח ו־`BASE_URL` מתאים.
- [ ] משתמש דמו מחובר ב־Firebase, יש לו `daily_health/{today}` ו־`daily_checkins/{today}` עם נתונים סבירים.
- [ ] המרצה יראה: ציון בצבע + המלצת AI + גרף שבועי + מסך מאמן.
- [ ] יש לך פתוח ברקע: `run_manifest.json` כדי לצטט מספרים, ו־`docs/ML_ONBOARDING_HE.md` למקרה שתרצי הפניה.
- [ ] תרגלי בקול רם פעם אחת את 4 המשפטים מסעיף 0 ואת ההסבר מסעיף 5 ("למה דמו ולא מודל אמיתי").
- [ ] קחי דף עם המספרים: Recall 0.97, Precision 0.14, FPR 0.93, AUC 0.64, threshold 0.36, dataset 345K שורות, 1000 ספורטאים, ExtraTrees winner.

בהצלחה.
