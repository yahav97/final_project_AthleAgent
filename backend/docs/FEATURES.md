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

| Collection | Document | מה נמשך | טווח זמן |
|---|---|---|---|
| `users/{uid}` | פרופיל | age, historyInjuryCount | קבוע (פעם אחת) |
| `users/{uid}/daily_health/{date}` | בריאות היום | שינה, צעדים, מרחק, דופק, HRV, קלוריות, משקל, גובה, SpO2, נשימה, מהירות, הספק וכו' | **יום נוכחי** |
| `users/{uid}/daily_health/{date-1}` | בריאות אתמול | אותם שדות — fallback אם היום חסר | **אתמול** |
| `users/{uid}/daily_health/{date-6}...{date-1}` | היסטוריה | מרחק, שינה, דופק | **7 ימים אחורה** |
| `users/{uid}/daily_checkins/{date}` | דיווח עצמי | stressLevel, muscleSoreness, energyLevel | **יום נוכחי** |
| `users/{uid}/daily_nutrition/{date}` | תזונה | totalProtein, totalCarbs, mealsLoggedCount, totalCalories | **יום נוכחי** (fallback עד 14 ימים) |

### שדות מ-`daily_health` (Health Connect / שעון חכם)

| שדה בפיירבייס | סוג נתון | מקור |
|---|---|---|
| `sleepMinutes` | דקות שינה | Health Connect → Sleep |
| `steps` | צעדים | Health Connect → Steps |
| `distanceMeters` | מרחק במטרים | Health Connect → Distance |
| `activeCalories` | קלוריות פעילות | Health Connect → ActiveCalories |
| `totalCalories` | סה"כ שריפה | Health Connect → TotalCalories |
| `heartRateAvg` | דופק ממוצע | Health Connect → HeartRate |
| `heartRateMax` | דופק מקסימלי | Health Connect → HeartRate |
| `heartRateMin` | דופק מינימלי | Health Connect → HeartRate |
| `hrvRmssd` | HRV (ms) | Health Connect → HeartRateVariabilityRmssd |
| `restingHeartRate` | דופק מנוחה | Health Connect → RestingHeartRate |
| `weightKg` | משקל | Health Connect → Weight |
| `heightCm` | גובה | Health Connect → Height |
| `bmrCalories` | BMR | Health Connect → BasalMetabolicRate |
| `bodyFatPct` | אחוז שומן | Health Connect → BodyFat |
| `vo2Max` | VO₂max | Health Connect → Vo2Max |
| `elevationGainedMeters` | עלייה במטרים | Health Connect → ElevationGained |
| `floorsClimbed` | קומות | Health Connect → FloorsClimbed |
| `avgSpeed` | מהירות ממוצעת | Health Connect → Speed |
| `maxSpeed` | מהירות מקסימלית | Health Connect → Speed |
| `avgPower` | הספק ממוצע (וואט) | Health Connect → Power |
| `avgCadence` | קצב צעדים | Health Connect → StepsCadence |
| `respiratoryRate` | קצב נשימה | Health Connect → RespiratoryRate |
| `oxygenSaturation` | SpO₂ % | Health Connect → OxygenSaturation |
| `injuredYesterday` | פציעה אתמול (0/1) | דיווח עצמי שנשמר ב-daily_health |

### שדות מ-`daily_checkins` (דיווח עצמי)

| שדה בפיירבייס | סוג נתון |
|---|---|
| `stressLevel` | רמת סטרס (1–10 או 0–100) |
| `muscleSoreness` | כאב שרירים (1–5) |
| `energyLevel` | רמת אנרגיה (1–10 או 0–100) |

### שדות מ-`daily_nutrition` (תזונה)

| שדה בפיירבייס | סוג נתון |
|---|---|
| `totalProtein` | גרם חלבון |
| `totalCarbs` | גרם פחמימות |
| `mealsLoggedCount` | מספר ארוחות שנרשמו |
| `totalCalories` | סה"כ קלוריות שנצרכו |

### שדות מ-`users/{uid}` (פרופיל)

| שדה בפיירבייס | סוג נתון |
|---|---|
| `age` | גיל |
| `historyInjuryCount` | מספר פציעות קודמות |

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
| 4 | `injured_yesterday` | **7.1%** | `daily_health.injuredYesterday` | bool → 0/1 |
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
| `daily_health` | `activeCalories` | `workout_intensity_minutes`, load proxies |
| `daily_health` | `totalCalories` | `total_calories_burned` (שריפה, לא צריכה!) |
| `daily_health` | `heartRateAvg` | `resting_hr`, `hrv_score` proxy |
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
