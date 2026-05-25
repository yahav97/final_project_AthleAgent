# זרימת נתונים ופיצ'רים — חוזה Production

> **נספח ML מלא** (יצירת דאטה, השוואת פיצ'רים, בחירת מודל, גרפים וציונים):  
> [`ML_model/notebooks/model_improvement_journey.ipynb`](../../ML_model/notebooks/model_improvement_journey.ipynb)  
>
> **מסמך זה = חוזה שירות בלבד** (Firestore → מודל). ללא ניתוח ML כפול — ראו את המחברת.

## סקירה כללית (תפעול)

| פרט | ערך |
|---|---|
| **מודל** | XGBoostDeep |
| **מספר פיצ'רים** | 36 (`model_features.py`) |
| **סף High Risk** | ≥ 0.18 |
| **סף Medium** | 0.11 – 0.18 |
| **חלון היסטוריה מקסימלי** | 7 ימים אחורה |

### זרימת חיזוי יומית (בוקר) — סיכון **להיום**, לא למחר

כשהמשתמש פותח את האפליקציה **בבוקר של יום D**, החיזוי מתייחס ל**סיכון הפציעה היום** (מיידי), לא לתחזית למחר.

**מה נכנס לקלט (תאריך API = `D` — היום):**

| מקור | תאריך במסמך | מה נכלל |
|---|---|---|
| שעון / בריאות | `daily_health/{D}` | שינה מהלילה האחרון, סנכרון בוקר (חלקי) |
| שעון / בריאות | `daily_health/{D-1}` | **fallback** — עומס אתמול (צעדים, מרחק, קלוריות…) אם היום עדיין חסר |
| סקר | `daily_checkins/{D}` | סטרס, כאב, אנרגיה, **`injuredYesterday`** (= פציעה ב-**D−1**) |
| תזונה | `daily_nutrition/{D}` | צריכה (אתמול/היום לפי מה שנרשם) |
| היסטוריה | 7 ימים עד **D−1** | ACWR, חוב שינה, `hrv_drop` (rolling) |

**מה יוצא:**

| איפה | משמעות |
|---|---|
| `daily_health/{D}` → `finalRiskScore`, `riskLevel`, … | **סיכון להיום D** — מוצג מיד באפליקציה |
| `InjuryPredictionResponse` | אותו דבר בשלושת השדות (`risk_level`, `risk_score`, `prediction_confidence`) |

> **הפרדה חשובה:** ב-**production** (בוקר) הכל תחת תאריך **D**.  
> **`daily_checkins/{D+1}`** משמש רק ב-**בניית דאטהסט לאימון** (למטה) — כי רק למחרת בוקר אפשר לדעת בוודאות אם הייתה פציעה ביום D.

---

## 1. מקורות הנתונים (Firestore)

| Collection | Document | תפקיד | טווח זמן |
|---|---|---|---|
| `users/{uid}` | פרופיל | רישום: `age`, `historyInjuryCount` | קבוע |
| `users/{uid}/daily_health/{date}` | בריאות + פלט חיזוי | שעון; אחרי `/predict/daily`: `finalRiskScore`… | **יום נוכחי** (+ אתמול fallback) |
| `users/{uid}/daily_health/{date-6}…{date}` | היסטוריה | rolling features (מרחק, שינה, HRV) | **7 ימים** |
| `users/{uid}/daily_checkins/{date}` | דיווח עצמי | stress, soreness, energy | **יום נוכחי** |
| `users/{uid}/daily_nutrition/{date}` | תזונה | protein, carbs, meals, calories | **יום נוכחי** (fallback 14 ימים) |

### חוזה שדות — לפי מקור

כל הקלטים למודל מגיעים מ-**ארבעה מקורות** (בנוסף לפלט החיזוי):

| # | מקור | Collection | שדות עיקריים | פיצ'רי מודל (דוגמה) |
|---|---|---|---|---|
| 1 | **שעון** | `daily_health` | שינה, צעדים, דופק, HRV… | `sleep_hours`, `hrv_score`, `daily_distance_km` |
| 2 | **רישום** | `users/{uid}` | `age`, `historyInjuryCount` | `age`, `history_injury_count` |
| 3 | **סקר יומי** | `daily_checkins/{date}` | `stressLevel`, `muscleSoreness`, `energyLevel`, **`injuredYesterday`** | `stress_level`, `muscle_soreness`, `energy_level`, `injured_yesterday` |
| 4 | **תזונה** | `daily_nutrition/{date}` | `totalProtein`, `totalCarbs`, `mealsLoggedCount`, `totalCalories` | `nutrition_intake_calories`, `daily_calories`, `calorie_balance` |
| — | **פלט חיזוי** | `daily_health` (אחרי API) | `finalRiskScore`, `riskLevel`, … | לא קלט — תוצאה |

#### 1. מהשעון (Health Connect → `daily_health`)

21 רשומות זמינות בשעון; האפליקציה ממפה לשדות Firestore (טבלה מפורטת למטה).

#### 2. מרישום (`users/{uid}`)

| שדה | מקור |
|---|---|
| `age` | טופס הרשמה / פרופיל |
| `historyInjuryCount` | טופס הרשמה / פרופיל |

#### 3. סקר יומי (`users/{uid}/daily_checkins/{date}`)

| שדה | סוג | פיצ'ר במודל |
|---|---|---|
| `stressLevel` | סטרס (1–10 או 0–100 באפליקציה) | `stress_level` |
| `muscleSoreness` | כאב שרירים (1–5) | `muscle_soreness` |
| `energyLevel` | אנרגיה (1–10 או 0–100) | `energy_level` |
| `injuredYesterday` | פציעה אתמול (0/1) | `injured_yesterday` |

נמשך מ-`daily_checkins/{D}` ביום החיזוי (אין fallback לאתמול ב-backend).

**רק לאימון מחדש (לא בחיזוי בוקר):** כדי לבנות תיוג היסטורי "האם הייתה פציעה ביום D", הסקריפט `build_training_dataset_from_firestore` קורא `injuredYesterday` מ-`daily_checkins/{D+1}` — כי בבוקר של D+1 המשתמש מדווח על אתמול (יום D). ב-production לא משתמשים ב-D+1.

#### 4. תזונה (`users/{uid}/daily_nutrition/{date}`)

| שדה | סוג | פיצ'ר במודל |
|---|---|---|
| `totalProtein` | גרם חלבון | `daily_calories` (derive), `nutrition_intake_calories` |
| `totalCarbs` | גרם פחמימות | כמו למעלה |
| `mealsLoggedCount` | מספר ארוחות | fallback לאומדן קלוריות |
| `totalCalories` | קלוריות **צריכה** (לא שריפה!) | `nutrition_intake_calories` |

**Fallback:** אם היום חסר — חיפוש עד **14 ימים** אחורה באותה collection (`merge_nutrition_with_history`).

**הבחנה:** `daily_health.totalCalories` = **שריפה** (מקלוריות שעון). `daily_nutrition.totalCalories` = **צריכה** (ממזון).

#### 5. ב-`daily_health` — אחרי חיזוי (`POST /predict/daily`)

| שדה Firestore | תוכן | ב-`InjuryPredictionResponse`? |
|---|---|---|
| `finalRiskScore` | הסתברות × 100 — **סיכון להיום** | כן — כ-`risk_score` (0–1) בתגובת API |
| `riskLevel` | `Low` / `Medium` / `High` — **להיום** | כן — כ-`risk_level` |
| `predictionConfidence` | 0–100 | כן — כ-`prediction_confidence` |
| `predictionUpdatedAt` | ISO UTC | **לא** — רק ב-Firestore |

מיפוי API ↔ Firestore:

| `InjuryPredictionResponse` (JSON) | Firestore `daily_health` |
|---|---|
| `risk_level` | `riskLevel` |
| `risk_score` (0.0–1.0) | `finalRiskScore` = `round(risk_score × 100, 2)` |
| `prediction_confidence` | `predictionConfidence` |

### רשומות Health Connect מהשעון (21)

| רשומת HC | שדה ב-`daily_health` | סינכרון Android (`WearableSyncActivity`) | מודל |
|---|---|---|---|
| **SleepSession** | `sleepMinutes` | כן | כן |
| **ActiveCaloriesBurned** | `activeCalories` | כן | כן |
| **BasalMetabolicRate** | `bmrCalories` | כן | כן |
| **Steps** | `steps` | כן | כן |
| **Distance** | `distanceMeters` | כן | כן |
| **HeartRateSeries** | `heartRateAvg` / `Max` / `Min` | כן (אגרגציה יומית) | כן |
| **Weight** | `weightKg` | כן | כן |
| **Height** | `heightCm` | לא | כן |
| **HeartRateVariabilityRmssd** | `hrvRmssd` | לא | כן |
| **RestingHeartRate** | `restingHeartRate` | לא | כן |
| **BodyFat** | `bodyFatPct` | לא | כן |
| **Vo2Max** | `vo2Max` | לא | כן |
| **ElevationGained** | `elevationGainedMeters` | לא | כן |
| **FloorsClimbed** | `floorsClimbed` | לא | כן |
| **SpeedSeries** | `avgSpeed` / `maxSpeed` | לא | כן |
| **PowerSeries** | `avgPower` | לא | כן |
| **StepsCadenceSeries** | `avgCadence` | לא | כן |
| **RespiratoryRate** | `respiratoryRate` | לא | כן |
| **OxygenSaturation** | `oxygenSaturation` | לא | כן |
| **ExerciseSession** | — (מומלץ: משך/סוג אימון) | הרשאה בלבד, לא נשמר | מוערך (`workout_intensity`) |
| **LeanBodyMass** | — | לא | לא |

**שדה נגזר (אין רשומת HC נפרדת בשעון):**

| שדה ב-`daily_health` | חישוב |
|---|---|
| `totalCalories` | `activeCalories + bmrCalories` (או אגרגט HC אם האפליקציה קוראת `TotalCaloriesBurned`) |

**הערות:**
- אין בשעון: TotalCaloriesBurned, BloodGlucose, BloodPressure, טמפרטורה, מסה מים/עצם, CyclingPedalingCadence, WheelchairPushes.
- דופק: אגרגציה מ-**HeartRateSeries** (בקוד Android: `HeartRateRecord`).
- `injuredYesterday` — בסקר יומי (`daily_checkins`), לא מ-HC.

### שדות ב-`daily_health` (מיפוי לפי שם Firestore)

| שדה בפיירבייס | מקור Health Connect |
|---|---|
| `sleepMinutes` | SleepSession |
| `steps` | Steps |
| `distanceMeters` | Distance |
| `activeCalories` | ActiveCaloriesBurned |
| `totalCalories` | נגזר: ActiveCaloriesBurned + BasalMetabolicRate |
| `heartRateAvg` / `heartRateMax` / `heartRateMin` | HeartRateSeries (אגרגציה) |
| `hrvRmssd` | HeartRateVariabilityRmssd |
| `restingHeartRate` | RestingHeartRate |
| `weightKg` | Weight |
| `heightCm` | Height |
| `bmrCalories` | BasalMetabolicRate |
| `bodyFatPct` | BodyFat |
| `vo2Max` | Vo2Max |
| `elevationGainedMeters` | ElevationGained |
| `floorsClimbed` | FloorsClimbed |
| `avgSpeed` / `maxSpeed` | SpeedSeries |
| `avgPower` | PowerSeries |
| `avgCadence` | StepsCadenceSeries |
| `respiratoryRate` | RespiratoryRate |
| `oxygenSaturation` | OxygenSaturation |
| `finalRiskScore` | פלט מודל (לא קלט) |
| `riskLevel` | פלט מודל |
| `predictionConfidence` | פלט מודל |
| `predictionUpdatedAt` | פלט מודל (לא ב-API response) |

---

> פירוט מלא לשדות שעון, סקר ותזונה — בטבלאות למעלה (סעיפים 1–5).

---

## 2. חישובים ותמורות (Preprocessing)

### המרות סקאלה

| נתון גולמי | → פיצ'ר במודל | המרה |
|---|---|---|
| `sleepMinutes` | `sleep_hours` | חלוקה ב-60, חסום 3–12 |
| `distanceMeters` | `daily_distance_km` | חלוקה ב-1000. אם חסר — `steps × 0.0008` |
| `stressLevel` | `stress_level` | אם > 10 → חלוקה ב-10 (המרה מ-0–100 ל-1–10) |
| `muscleSoreness` | `muscle_soreness` | אם ≤ 5 → כפל ב-2 (המרה מ-1–5 ל-1–10) |
| `energyLevel` | `energy_level` | אם > 10 → חלוקה ב-10 |
| `injuredYesterday` | `injured_yesterday` | true→1, false→0 |
| `weightKg` + `heightCm` | `bmi` | `weight / (height_m²)`, חסום 15–45 |
| `hrvRmssd` | `hrv_score` | ישיר (חסום 30–105). אם חסר: `110 − resting_hr × 0.65` |
| `restingHeartRate` / `heartRateMin` | `resting_hr` | Resting HR ← Min HR ← Avg HR (לפי זמינות) |

### חישובים נגזרים

| פיצ'ר | נוסחה |
|---|---|
| `workout_intensity_minutes` | `daily_distance_km × 5.5 + active_calories / 40` (חסום 0–240) |
| `calorie_balance` | `daily_calories − total_calories_burned` |
| `load_recovery_imbalance` | `acwr_ratio × sleep_debt_3d` |
| `speed_intensity_ratio` | `max_speed / (avg_speed + 0.1)` (חסום עד 5.0) |
| `avg_speed` (fallback) | אם אין מהשעון → `daily_distance_km / (workout_intensity / 60)` |
| `max_speed` (fallback) | אם אין מהשעון → `avg_speed × 1.3` |
| `avg_cadence` (fallback) | אם אין מהשעון → `steps / workout_intensity_minutes` |

---

## 3. פיצ'רים נגזרים מהיסטוריה (7 ימים)

| פיצ'ר | מה מחשב | נתון בסיס | חלון |
|---|---|---|---|
| `acute_load_7d` | ממוצע מרחק ב-7 ימים אחרונים | `daily_distance_km` | 7 ימים |
| `chronic_load_21d` | **קירוב** מ-7 ימים: `weekly_mean × 0.85 + weekly_std × 0.35 + 0.5` | `daily_distance_km` | 7 ימים (אומדן) |
| `acwr_ratio` | `acute_load_7d / chronic_load_21d` חסום 0.35–2.8 | מחושב | — |
| `acwr_ratio_ma7` | ממוצע ACWR על 7 ימים | `acwr_ratio` | 7 ימים |
| `sleep_debt_3d` | סכום חוב שינה (8 − sleep) ב-3 ימים אחרונים | `sleep_hours` | 3 ימים |
| `sleep_hours_ma7` | ממוצע שינה על 7 ימים | `sleep_hours` | 7 ימים |
| `hrv_drop` | HRV היום − ממוצע HRV של 7 ימים, חסום ±15 | `hrv_score` | 7 ימים |

### מדיניות confidence — מה קורה כשחסר מידע היסטורי?

| ימי היסטוריה זמינים | רמת ביטחון | מה קורה |
|---|---|---|
| 7 ימים | **high** | משתמש בפיצ'רים מחושבים מהיסטוריה אמיתית |
| 4–6 ימים | **medium** | משתמש בפיצ'רים מחושבים (rolling עם `min_periods=1`) |
| 0–3 ימים | **low** | **ערכי ברירת מחדל ניטרליים** לכל פיצ'רי ההיסטוריה |

---

## 4. ערכי ברירת מחדל (כשחסר נתון)

### תזונה — Fallback Logic

| מצב | מה קורה |
|---|---|
| יש `totalCalories` מ-nutrition | משתמש ישירות |
| אין totalCalories, יש protein + carbs | `(protein × 4 + carbs × 4) × 1.2` |
| אין כלום, יש `mealsLoggedCount` | `2500 × (0.6 + meals × 0.2)` |
| אין כלום בכלל | **2500 קלוריות** (default) |
| Fallback מימים קודמים | חיפוש עד 14 ימים אחורה ב-`daily_nutrition` |

### ברירות מחדל לכל הפיצ'רים

| פיצ'ר | Default | הערה |
|---|---|---|
| `sleep_hours` | 7.0 | שינה ניטרלית |
| `stress_level` | 5.0 | סטרס ניטרלי |
| `muscle_soreness` | 5.0 | כאב ניטרלי |
| `energy_level` | 5.0 | אנרגיה ניטרלית |
| `injured_yesterday` | 0.0 | לא נפצע |
| `history_injury_count` | 0.0 | אין היסטוריה |
| `daily_distance_km` | 3.5 | מרחק ממוצע |
| `workout_intensity_minutes` | 45.0 | — |
| `avg_cadence` | 168.0 | — |
| `elevation_gained_m` | 50.0 | — |
| `floors_climbed` | 5 | — |
| `avg_speed` | 8.0 | — |
| `max_speed` | 11.0 | — |
| `avg_power` | 0.0 | אין מד כוח |
| `active_calories_burned` | 350.0 | — |
| `hrv_score` | 62.0 | — |
| `resting_hr` | 54.0 | — |
| `respiratory_rate` | 15.0 | — |
| `spo2` | 97.0 | — |
| `bmi` | 23.5 | — |
| `body_fat_pct` | 16.0 | — |
| `vo2_max` | 48.0 | — |
| `age` | 28.0 | — |
| `load_recovery_imbalance` | 1.0 | — |
| `speed_intensity_ratio` | 1.3 | — |
| `nutrition_intake_calories` | 2500 | — |
| `daily_calories` | 2500 | — |
| `total_calories_burned` | 2450 | — |
| `calorie_balance` | 0 | ניטרלי |

**כל ה-defaults נבחרו להיות "ניטרליים"** — לא מושכים את החיזוי לסיכון גבוה או נמוך.

רשימת 36 הפיצ'רים, חשיבות, והשוואת גרסאות — **רק במחברת הנספח** (לינק למעלה).

---

## 5. מיפוי Firestore → Model (Contract)

| Firestore source | Field | Model feature |
|---|---|---|
| `users/{uid}` | `age` | `age` |
| `users/{uid}` | `historyInjuryCount` | `history_injury_count` |
| `daily_health` | `sleepMinutes` | `sleep_hours` |
| `daily_health` | `steps` | `daily_distance_km` fallback, `avg_cadence` |
| `daily_health` | `distanceMeters` | `daily_distance_km` primary |
| `daily_health` | `activeCalories` | `active_calories_burned`, `workout_intensity_minutes`, load proxies |
| `daily_health` | `totalCalories` (active+BMR) / `bmrCalories` + `activeCalories` | `total_calories_burned` |
| `daily_health` | `restingHeartRate` / `heartRateMin` / `heartRateAvg` | `resting_hr` (סדר עדיפות); `hrvRmssd` → `hrv_score` / `hrv_drop` |
| `daily_health` | `weightKg` | `bmi` |
| `daily_checkins` | `stressLevel` | `stress_level` |
| `daily_checkins` | `muscleSoreness` | `muscle_soreness` |
| `daily_checkins` | `energyLevel` | `energy_level` |
| `daily_nutrition` | `totalProtein` | `daily_calories` (derive) |
| `daily_nutrition` | `totalCarbs` | `daily_calories` (derive) |
| `daily_nutrition` | `mealsLoggedCount` | `daily_calories` (derive) |

**הבחנה קריטית:** `totalCalories` ב-`daily_health` = שריפה (מ-Health Connect). `totalCalories` ב-`daily_nutrition` = צריכה (ממזון). לא לבלבל!

---

## 6. Data Quality & Blocking

### שדות קריטיים (חוסר בהם עשוי לחסום חיזוי)

**אות עומס (Load)** — חובה אחד: `steps` או `distanceMeters`

**אות התאוששות (Recovery)** — חובה אחד מ:
- `sleepMinutes`, או
- `stressLevel` + `muscleSoreness`

### שדות רגישים (הורדת ציון איכות)

`sleepMinutes`, `steps`, `distanceMeters`, `heartRateAvg`, `stressLevel`, `muscleSoreness`

כל חסר מוריד 0.12 מציון האיכות. מתחת ל-0.35 → חיזוי נחסם.

### שדות סובלניים (לא מורידים ציון)

`totalProtein`, `totalCarbs`, `mealsLoggedCount`, `energyLevel`, `heartRateMax`, `heartRateMin`, `activeCalories`

