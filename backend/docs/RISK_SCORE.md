# חישוב ציון הסיכון (Risk Score) — מדריך מלא

> **קוד מקור:** `backend/services/prediction_service.py`, `preprocessing.py`, `history_service.py`, `model_features.py`  
> **מודל:** XGBoostDeep (`ML_model/artifacts/promoted.json`)  
> **36 פיצ'רים:** `backend/services/model_features.py`

---

## 1. תשובה קצרה: איך מחושב הציון?

**אין נוסחת משקלים לינארית בפרודקשן.**  
ציון הסיכון הוא **הסתברות לפציעה** (מחלקה חיובית) שמחזיר מודל XGBoost:

```
risk_score = model.predict_proba(X)[0, 1]   # ערך בין 0.0 ל־1.0
```

המודל מקבל **וקטור של 36 פיצ'רים** (שורה אחת ליום D), שנבנים מ:
- נתוני **היום** (שעון, סקר, תזונה)
- **fallback לאתמול** (D−1) לשדות שעון חסרים
- **היסטוריה של עד 7 ימים** (D−7 … D−1) לפיצ'רי עומס/התאוששות
- **ברירות מחדל ניטרליות** כשחסר מידע

המשקלים שמשפיעים על התוצאה הם **משקלי העצים של XGBoost** (לא קבועים בקוד שירות).  
באימון, לפי `feature_importance.csv` של המודל המקודם, הפיצ'רים המשמעותיים ביותר:

| דירוג | פיצ'ר | חשיבות (אימון) | קטגוריה |
|------|--------|----------------|---------|
| 1 | `hrv_drop` | 14.9% | ירידת HRV מול ממוצע 7 ימים |
| 2 | `stress_level` | 8.1% | סקר — סטרס |
| 3 | `load_recovery_imbalance` | 8.0% | `acwr_ratio × sleep_debt_3d` |
| 4 | `injured_yesterday` | 7.1% | סקר — פציעה אתמול |
| 5 | `acwr_ratio` | 7.0% | עומס חד / כרוני |
| 6 | `history_injury_count` | 5.0% | פרופיל |
| 7 | `sleep_debt_3d` | 4.4% | חוב שינה 3 ימים |
| 8 | `daily_distance_km` | 2.4% | עומס יומי |

> חשיבות זו מתארת **תרומה יחסית באימון**, לא "נקודות" שנוספות לציון בזמן ריצה.

---

## 2. על איזה יום מחושב הסיכון?

| מושג | ערך |
|------|-----|
| **תאריך חיזוי** | `D` — היום הנוכחי (`yyyy-MM-dd` בבקשת API) |
| **משמעות** | סיכון פציעה **היום (D)**, לא מחר |
| **מתי רץ** | אחרי סנכרון שעון + סקר (או טריגר דומה מהאפליקציה) |

### מקורות נתונים לפי תאריך

| מקור Firestore | תאריך | מה נכנס |
|----------------|-------|---------|
| `daily_health/{D}` | היום | שינה מהלילה, צעדים/מרחק בוקר, דופק, HRV… |
| `daily_health/{D-1}` | **fallback** | אם שדה חסר היום — נלקח מאתמול (עומס, שינה וכו') |
| `daily_checkins/{D}` | היום | `stressLevel`, `muscleSoreness`, `energyLevel`, `injuredYesterday` (= פציעה ב־D−1) |
| `daily_nutrition/{D}` | היום | חלבון, פחמימות, ארוחות, קלוריות צריכה |
| `daily_nutrition/{D-1}…{D-14}` | fallback תזונה | עד 14 ימים אחורה אם היום חסר |
| `users/{uid}` | פרופיל | `age`, `historyInjuryCount` |
| `daily_health` + `daily_checkins` | **D−7 … D−1** | חלון היסטוריה לפיצ'רי rolling (ללא יום D) |

**חלון היסטוריה:** `lookback_days=7`, `include_target_day=False`  
→ בפועל: **7 ימים שמסתיימים אתמול (D−1)**, לא כולל את היום הנוכחי.

---

## 3. זרימת חישוב (צעד אחר צעד)

```
Firestore (profile + health D + health D-1 + checkin D + nutrition D)
        ↓
InjuryPredictionRequest  (prediction_service.injury_prediction_request_from_firestore_snapshot)
        ↓
injury_request_to_model_dataframe  (preprocessing.py)
  • המרות סקאלה (שינה, סטרס, מרחק, BMI…)
  • פיצ'רים נגזרים (ACWR, calorie_balance, workout_intensity…)
  • ברירות מחדל לחסרים
        ↓
_apply_history_confidence_fallback  (prediction_service.py)
  • שליפת 7 ימים מ־Firestore
  • חישוב rolling: acute/chronic/ACWR, sleep_debt, hrv_drop
  • או ברירות מחדל אם < 4 ימי היסטוריה
        ↓
validate_feature_vector_for_model  → 36 עמודות מסודרות
        ↓
XGBoost.predict_proba  →  risk_score
        ↓
סיווג risk_level + prediction_confidence
        ↓
API response + שמירה ל־daily_health/{D}
```

---

## 4. 36 הפיצ'רים (קבוצות)

רשימה מלאה ב־`MODEL_FEATURE_COLUMNS`:

| קבוצה | פיצ'רים |
|-------|---------|
| פרופיל | `bmi`, `age`, `body_fat_pct`, `vo2_max`, `history_injury_count`, `injured_yesterday` |
| עומס אימון | `daily_distance_km`, `workout_intensity_minutes`, `avg_cadence`, `elevation_gained_m`, `floors_climbed`, `avg_speed`, `max_speed`, `avg_power`, `active_calories_burned` |
| התאוששות | `sleep_hours`, `hrv_score`, `resting_hr`, `respiratory_rate`, `spo2` |
| תזונה | `nutrition_intake_calories`, `daily_calories`, `total_calories_burned`, `calorie_balance` |
| סובייקטיבי | `stress_level`, `muscle_soreness`, `energy_level` |
| מנוע (engineered) | `acute_load_7d`, `chronic_load_21d`, `acwr_ratio`, `acwr_ratio_ma7`, `sleep_hours_ma7`, `sleep_debt_3d`, `hrv_drop`, `load_recovery_imbalance`, `speed_intensity_ratio` |

### המרות עיקריות (יום D)

| קלט | פיצ'ר | נוסחה / כלל |
|-----|--------|-------------|
| `sleepMinutes` | `sleep_hours` | ÷ 60, חסום 3–12 |
| `distanceMeters` / `steps` | `daily_distance_km` | מטרים÷1000; אם אין מרחק → `steps × 0.0008` |
| `stressLevel` | `stress_level` | אם > 10 → ÷ 10 (סקאלה 1–10) |
| `muscleSoreness` | `muscle_soreness` | אם ≤ 5 → `×2 − 0.5` (סקאלה 1–10) |
| `energyLevel` | `energy_level` | כמו סטרס |
| `hrvRmssd` | `hrv_score` | ישיר; אם חסר → `110 − resting_hr × 0.65` |
| `weightKg` + `heightCm` | `bmi` | `weight / height_m²`, חסום 15–45 |

### פיצ'רים נגזרים (יום D — לפני היסטוריה)

| פיצ'ר | נוסחה |
|--------|--------|
| `workout_intensity_minutes` | `daily_distance_km × 5.5 + active_calories / 40` (0–240) |
| `acute_load_7d` (מקדים) | `max(0.05, distance × 0.95 + active_cal / 450)` |
| `chronic_load_21d` (מקדים) | `max(0.55, acute × 0.78 + 1.35)` |
| `acwr_ratio` | `acute / chronic`, חסום 0.35–2.8 |
| `sleep_debt_3d` (מקדים) | `max(0, (8 − sleep_hours) × 1.25)` |
| `hrv_drop` (מקדים) | מבוסס HRV baseline 62 + resting HR |
| `calorie_balance` | `daily_calories − total_calories_burned` |
| `load_recovery_imbalance` | `acwr_ratio × sleep_debt_3d` |
| `speed_intensity_ratio` | `max_speed / (avg_speed + 0.1)`, עד 5.0 |

> אחרי שלב ההיסטוריה, ערכי `acute_load_7d`, `chronic_load_21d`, `acwr_ratio`, `sleep_debt_3d`, `hrv_drop` **מוחלפים** בחישוב מ־7 הימים (אם יש מספיק היסטוריה).

### פיצ'רים מהיסטוריה (7 ימים, D−7…D−1)

מחושבים ב־`history_service.compute_historical_derived_features`:

| פיצ'ר | חישוב |
|--------|--------|
| `acute_load_7d` | ממוצע `daily_distance_km` על 7 ימים (`rolling(7)`) |
| `chronic_load_21d` | **קירוב מ־7 ימים:** `weekly_mean × 0.85 + weekly_std × 0.35 + 0.5`, מינימום 0.55 |
| `acwr_ratio` | `acute / chronic`, חסום 0.35–2.8 |
| `sleep_debt_3d` | סכום `(8 − sleep_hours)` על 3 ימים אחרונים |
| `hrv_drop` | `hrv_score היום − ממוצע HRV 7 ימים`, חסום ±15 |

**לא מחושב מהיסטוריה בפועל** (נשאר proxy מיום D):  
`acwr_ratio_ma7` (= `acwr_ratio` של היום), `sleep_hours_ma7` (= `sleep_hours` של היום).

### מדיניות ביטחון היסטוריה

| ימים זמינים (בחלון) | רמת confidence | התנהגות |
|---------------------|----------------|----------|
| 7 | `high` | פיצ'רי rolling מהיסטוריה אמיתית |
| 4–6 | `medium` | אותו חישוב (`min_periods=1`) |
| 0–3 | `low` | **ברירות מחדל ניטרליות** לכל פיצ'רי ההיסטוריה |

ערכי ברירת מחדל להיסטוריה (`DEFAULT_FEATURE_VALUES`):

| פיצ'ר | Default |
|--------|---------|
| `acute_load_7d` | 4.5 |
| `chronic_load_21d` | 5.1 |
| `acwr_ratio` / `acwr_ratio_ma7` | 1.0 |
| `sleep_debt_3d` | 1.0 |
| `sleep_hours_ma7` | 7.0 |
| `hrv_drop` | 0.0 |

---

## 5. מה מוחזר לפרונט?

### 5.1 `POST /predict/daily`

**בקשה** (מינימלית — השרת טוען הכל מ־Firestore):

```json
{ "userId": "<firebase-uid>", "date": "2026-06-16" }
```

**תגובה** (`InjuryPredictionResponse` — **3 שדות בלבד**):

| שדה API | טיפוס | משמעות |
|---------|--------|--------|
| `risk_score` | `float` 0.0–1.0 | הסתברות פציעה (מודל) |
| `risk_level` | `"Low"` / `"Medium"` / `"High"` | רמת סיכון קטגוריאלית |
| `prediction_confidence` | `float` 0–100 | ביטחון בחיזוי (לא הסתברות פציעה!) |

### 5.2 שמירה ב־Firestore (`daily_health/{D}`)

| שדה Firestore | מקור | המרה |
|---------------|------|------|
| `finalRiskScore` | `risk_score` | `round(risk_score × 100, 2)` → **אחוז 0–100** |
| `riskLevel` | `risk_level` | ישיר |
| `predictionConfidence` | `prediction_confidence` | ישיר |
| `predictionUpdatedAt` | שרת | ISO UTC — **לא** בתגובת API |

### 5.3 איך האנדרואיד משתמש

1. **טריגר:** `WearableSyncActivity`, `DailyCheckInActivity`, `MealAnalysisActivity` קוראים ל־`/predict/daily` ברקע.
2. **תצוגה:** `AthleteDashboardActivity` קורא מ־Firestore:
   - `finalRiskScore` → אחוז במד (0–100)
   - `riskLevel` → טקסט
   - `predictionConfidence` → "AI Confidence"
3. **גרף היסטוריה:** 7 ימים אחרונים של `finalRiskScore` מ־`daily_health`.

**האפליקציה לא משתמשת ישירות ב־`risk_score` (0–1)** — רק ב־`finalRiskScore` (0–100) מ־Firestore.

---

## 6. ספים (Thresholds)

### 6.1 `risk_level` — קוד שירות (נוכחי)

ב־`predict_injury_risk` (`prediction_service.py`):

| רמה | תנאי על `risk_score` (0–1) | שקול ב־`finalRiskScore` |
|-----|----------------------------|-------------------------|
| **Low** | `< 0.40` | `< 40` |
| **Medium** | `0.40 ≤ score < 0.70` | `40–69` |
| **High** | `≥ 0.70` | `≥ 70` |

> **הערת סנכרון:** ב־`MODEL.md` / `FEATURES.md` מופיעים ספים **0.11 / 0.18** (מאימון).  
> ב־`run_manifest.json` של המודל המקודם: `"threshold": 0.18` — זה **סף אופרטיבי לאימון** (Recall/FPR), שנשמר ב־bundle אך **לא משמש כרגע** לסיווג `risk_level` בשרת.  
> הספים 0.40 / 0.70 הם **hardcoded** בקוד השירות.

### 6.2 צבעי UI באנדרואיד (`finalRiskScore` 0–100)

| ציון | צבע / מצב |
|------|-----------|
| ≤ 20 | ירוק |
| 21–50 | צהוב |
| 51–70 | כתום |
| > 70 | אדום |

אלה **עיצוב UI**, לא בהכרח זהים ל־`risk_level` מהשרת.

### 6.3 `prediction_confidence` (0–100)

לא קשור לסיכון פציעה — מודד **אמינות הקלט**:

```
history_score = 0.95 (high) | 0.70 (medium) | 0.45 (low)
quality_score = ציון שלמות נתוני היום (0–1)

prediction_confidence = round((0.6 × history_score + 0.4 × quality_score) × 100, 2)
```

**ציון איכות נתונים (`quality_score`):**

| כלל | השפעה |
|-----|--------|
| התחלה | 1.0 |
| כל שדה **רגיש** חסר | −0.12 |
| חסר אות עומס (`steps` **או** `distanceMeters`) | `hard_missing` → ציון מקסימום 0.25 |
| חסר אות התאוששות (`sleepMinutes` **או** `stressLevel`+`muscleSoreness`) | `hard_missing` → ציון מקסימום 0.25 |

שדות רגישים: `sleepMinutes`, `steps`, `distanceMeters`, `heartRateAvg`, `stressLevel`, `muscleSoreness`, `hrvRmssd`, `restingHeartRate`.

> **חשוב:** `has_hard_blocker` מחושב ונרשם בלוג, אך **לא חוסם** את החיזוי בקוד הנוכחי — רק מוריד `prediction_confidence`.

### 6.4 שער מודל (Model gate)

המודל לא נטען / החיזוי נכשל ב־500 אם:
- אין `injury_model.pkl` תקין
- `Recall@Threshold` < 0.80 (hard gate ב־`model_loader.py`)
- `ROC-AUC` < 0.68

המודל המקודם: Recall ≈ 0.866, AUC ≈ 0.723, threshold אימון = **0.18**.

---

## 7. endpoints ישנים (לא production)

| Endpoint | חישוב | הערה |
|----------|--------|------|
| `POST /demo_predict` | היוריסטיקה: שינה + כאב + סטרס + מרחק | **לא ML** — לדמו בלבד |
| `POST /test_predict` | תשובה קבועה 72.5% | mock |
| `POST /predict/sklearn` | ML ישיר על payload מלא | מושבת כברירת מחדל |

### משקלי הדמו (`/demo_predict`) — לשם השוואה בלבד

```
score = 10
+ 30 אם sleep < 5h, או +15 אם sleep < 7h
+ muscle_soreness × 7
+ stress_level × 0.25
+ 15 אם daily_distance_km > 12
→ cap 100

Low ≤ 40, Medium ≤ 60, High > 60
```

---

## 8. דוגמה מספרית

נניח שהמודל החזיר `risk_score = 0.2341`:

| שדה | ערך |
|-----|-----|
| `risk_score` | `0.2341` |
| `finalRiskScore` | `23.41` → UI מציג **23%** |
| `risk_level` | **Low** (< 0.40) |
| צבע UI | ירוק (≤ 20) או צהוב (21–50) — תלוי עיגול |
| `prediction_confidence` | למשל `78.5` אם היסטוריה high ואיכות 0.85 |

---

## 9. קישורים

| מסמך | תוכן |
|------|------|
| [`FEATURES.md`](FEATURES.md) | חוזה Firestore, מיפוי שדות, defaults |
| [`MODEL.md`](MODEL.md) | קונפיג מודל, gate, סף אימון |
| [`BACKEND.md`](BACKEND.md) | API וארכיטקטורה |
| [`ML_model/notebooks/model_improvement_journey.ipynb`](../../ML_model/notebooks/model_improvement_journey.ipynb) | ניתוח ML מלא, השוואת מודלים |
