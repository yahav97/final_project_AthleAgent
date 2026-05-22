# זרימת נתונים ופיצ'רים — מודל חיזוי פציעות AthleAgent

## סקירה כללית

| פרט | ערך |
|---|---|
| **מודל** | XGBoostDeep |
| **מספר פיצ'רים סופי** | 34 |
| **סף החלטה (High Risk)** | 0.18 |
| **Recall** | 86.6% |
| **ROC-AUC** | 0.723 |
| **חלון היסטוריה מקסימלי** | 7 ימים אחורה |

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

נמשך ביום החיזוי בלבד (אין fallback לאתמול ב-backend).

**תיוג לאימון:** `injury_tomorrow` ליום `D` נלקח מ-`injuredYesterday` ב-`daily_checkins/{D+1}` (fallback: `daily_health/{D+1}` לנתונים ישנים).

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
| `finalRiskScore` | הסתברות × 100 (0–100) | כן — כ-`risk_score` (0–1) בתגובת API |
| `riskLevel` | `Low` / `Medium` / `High` | כן — כ-`risk_level` |
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

---

## 5. הפיצ'רים הסופיים (34) לפי סדר חשיבות

| # | פיצ'ר | חשיבות | מקור הנתון | חישוב |
|---|---|---|---|---|
| 1 | `hrv_drop` | **14.9%** | היסטוריה 7 ימים של `hrvRmssd` | HRV_today − mean(HRV_7d) |
| 2 | `stress_level` | **8.1%** | `daily_checkins.stressLevel` | המרת סקאלה |
| 3 | `load_recovery_imbalance` | **8.0%** | חישוב | acwr_ratio × sleep_debt_3d |
| 4 | `injured_yesterday` | **7.1%** | `daily_checkins.injuredYesterday` | bool → 0/1 |
| 5 | `acwr_ratio` | **7.0%** | היסטוריה 7 ימים של `distanceMeters` | acute_7d / chronic_estimate |
| 6 | `history_injury_count` | **5.0%** | `users/{uid}.historyInjuryCount` | ישיר |
| 7 | `sleep_debt_3d` | **4.4%** | היסטוריה 3 ימים של `sleepMinutes` | sum(max(0, 8 − sleep)) |
| 8 | `daily_distance_km` | **2.4%** | `daily_health.distanceMeters` | מטרים / 1000 |
| 9 | `sleep_hours` | **2.3%** | `daily_health.sleepMinutes` | דקות / 60 |
| 10 | `active_calories_burned` | **2.0%** | `daily_health.activeCalories` | ישיר |
| 11 | `workout_intensity_minutes` | **2.0%** | חישוב | distance × 5.5 + calories / 40 |
| 12 | `muscle_soreness` | **1.9%** | `daily_checkins.muscleSoreness` | המרת סקאלה |
| 13 | `chronic_load_21d` | **1.7%** | היסטוריה 7 ימים | אומדן כרוני |
| 14 | `acwr_ratio_ma7` | **1.6%** | היסטוריה 7 ימים | mean(acwr_7d) |
| 15 | `acute_load_7d` | **1.5%** | היסטוריה 7 ימים של `distanceMeters` | mean(distance_7d) |
| 16 | `energy_level` | **1.5%** | `daily_checkins.energyLevel` | המרת סקאלה |
| 17–34 | שאר הפיצ'רים | 1.4%–1.5% כ"א | מגוון מקורות | ישיר / fallback / חישוב |

**Top 7** (חוסמים ~54.9% מהחשיבות):
`hrv_drop`, `stress_level`, `load_recovery_imbalance`, `injured_yesterday`, `acwr_ratio`, `history_injury_count`, `sleep_debt_3d`

---

## 6. מיפוי Firestore → Model (Contract)

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

## 7. Data Quality & Blocking

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

---

## 8. תרשים זרימה מסכם

```
┌─────────────────────────────────────────────────────────────────┐
│                        FIREBASE                                  │
├──────────────┬──────────────┬───────────────┬────────────────────┤
│ users/{uid}  │ daily_health │ daily_checkins│ daily_nutrition    │
│              │ (7 ימים)     │ (היום)        │ (היום + fallback)  │
│ • age        │ • sleep      │ • stress      │ • calories         │
│ • injuries   │ • distance   │ • soreness    │ • protein          │
│              │ • HR/HRV     │ • energy      │ • carbs            │
│              │ • calories   │               │                    │
│              │ • speed/power│               │ default: 2500 kcal │
│              │ • SpO2/resp  │               │                    │
│              │ • elevation  │               │                    │
└──────┬───────┴──────┬───────┴───────┬───────┴────────┬───────────┘
       │              │               │                │
       ▼              ▼               ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PREPROCESSING                                  │
│  • המרות יחידות (דקות→שעות, מטרים→קמ)                           │
│  • המרות סקאלה (0-100→1-10)                                      │
│  • Fallbacks (אם חסר → שימוש באתמול / ברירת מחדל)               │
│  • חישוב BMI, workout_intensity, load_recovery_imbalance        │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│              FEATURE ENGINEERING (היסטוריה 7 ימים)               │
│  confidence = high (7 ימים) / medium (4-6) / low (0-3)          │
│  • acute_load_7d, chronic_load_21d, acwr_ratio                  │
│  • sleep_debt_3d, sleep_hours_ma7, hrv_drop                     │
│  confidence=low? → ערכי ברירת מחדל ניטרליים                      │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                  XGBoostDeep MODEL                                │
│          34 פיצ'רים → predict_proba → סיכון 0.0–1.0             │
│          ≥ 0.18 → High Risk                                      │
│          ≥ 0.11 → Medium Risk                                    │
│          < 0.11 → Low Risk                                       │
└─────────────────────────────────────────────────────────────────┘
```
