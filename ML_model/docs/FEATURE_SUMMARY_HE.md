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

## שלב 1 — מה נמשך מפיירבייס?

### מקורות הנתונים (Collections)

| Collection | Document | מה נמשך | טווח זמן |
|---|---|---|---|
| `users/{uid}` | פרופיל | age, historyInjuryCount | קבוע (פעם אחת) |
| `users/{uid}/daily_health/{date}` | בריאות היום | שינה, צעדים, מרחק, דופק, HRV, קלוריות, משקל, גובה, SpO2, נשימה, מהירות, הספק וכו' | **יום נוכחי** |
| `users/{uid}/daily_health/{date-1}` | בריאות אתמול | אותם שדות — fallback אם היום חסר | **אתמול** |
| `users/{uid}/daily_health/{date-6}...{date-1}` | היסטוריה | מרחק, שינה, דופק | **7 ימים אחורה** |
| `users/{uid}/daily_checkins/{date}` | דיווח עצמי | stressLevel, muscleSoreness, energyLevel | **יום נוכחי** |
| `users/{uid}/daily_nutrition/{date}` | תזונה | totalProtein, totalCarbs, mealsLoggedCount, totalCalories | **יום נוכחי** (fallback עד 14 ימים) |

### שדות שנמשכים מפיירבייס — פירוט מלא

#### מ-`daily_health` (Health Connect / שעון חכם)

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

#### מ-`daily_checkins` (דיווח עצמי באפליקציה)

| שדה בפיירבייס | סוג נתון |
|---|---|
| `stressLevel` | רמת סטרס (1–10 או 0–100) |
| `muscleSoreness` | כאב שרירים (1–5) |
| `energyLevel` | רמת אנרגיה (1–10 או 0–100) |

#### מ-`daily_nutrition` (תזונה)

| שדה בפיירבייס | סוג נתון |
|---|---|
| `totalProtein` | גרם חלבון |
| `totalCarbs` | גרם פחמימות |
| `mealsLoggedCount` | מספר ארוחות שנרשמו |
| `totalCalories` | סה"כ קלוריות שנצרכו |

#### מ-`users/{uid}` (פרופיל)

| שדה בפיירבייס | סוג נתון |
|---|---|
| `age` | גיל |
| `historyInjuryCount` | מספר פציעות קודמות |

---

## שלב 2 — חישובים ותמורות (Preprocessing)

כל נתון גולמי מפיירבייס עובר עיבוד לפני שנכנס למודל:

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

### חישובים נגזרים (לא מהשעון)

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

## שלב 3 — פיצ'רים נגזרים מהיסטוריה (7 ימים)

אלה הפיצ'רים שמחושבים מ-7 ימי `daily_health` שנמשכים מפיירבייס:

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
| 4–6 ימים | **medium** | משתמש בפיצ'רים מחושבים (rolling עם `min_periods=1` — ממוצע על מה שיש) |
| 0–3 ימים | **low** | **ערכי ברירת מחדל ניטרליים** לכל פיצ'רי ההיסטוריה |

כשאין מספיק ימים, כל הפיצ'רים הנגזרים מקבלים defaults קבועים שלא מושכים לכיוון סיכון:

| פיצ'ר | Default | משמעות |
|---|---|---|
| `acute_load_7d` | 4.5 | עומס "ממוצע" |
| `chronic_load_21d` | 5.1 | בסיס כרוני סביר |
| `acwr_ratio` | 1.0 | עומס מאוזן |
| `acwr_ratio_ma7` | 1.0 | עומס מאוזן |
| `sleep_debt_3d` | 1.0 | חוב שינה מינימלי |
| `sleep_hours_ma7` | 7.0 | שינה ממוצעת |
| `hrv_drop` | 0.0 | אין שינוי |

**בהיסטוריה עצמה** (כלומר ביום מסוים שחסר בו נתון ספציפי מתוך ה-7 ימים), המערכת מחשבת defaults פנימיים:
- אין `distanceMeters`? → `steps × 0.0008`. אין גם steps? → 0
- אין `sleepMinutes`? → 7.0 שעות
- אין `restingHeartRate`? → 54.0. אין `heartRateAvg`? → 54.0
- HRV תמיד מחושב מדופק: `110 − resting_hr × 0.65`

---

## שלב 4 — ערכי ברירת מחדל לנתון יומי (כשחסר)

### תזונה — יש defaults

**כן, יש ערכי ברירת מחדל לתזונה.** נתוני תזונה הם הדבר שהכי סביר שיהיה חסר. הלוגיקה:

| מצב | מה קורה |
|---|---|
| יש `totalCalories` מ-nutrition | משתמש ישירות |
| אין totalCalories, יש protein + carbs | `(protein × 4 + carbs × 4) × 1.2` (אומדן עם שומן) |
| אין כלום, יש `mealsLoggedCount` | `2500 × (0.6 + meals × 0.2)` — קירוב לפי כמות ארוחות |
| אין כלום בכלל | **2500 קלוריות** (default) |
| Fallback מימים קודמים | חיפוש עד 14 ימים אחורה ב-`daily_nutrition` |

ערכי ברירת מחדל לפיצ'רי תזונה:

| פיצ'ר | Default |
|---|---|
| `nutrition_intake_calories` | 2500 |
| `daily_calories` | 2500 |
| `total_calories_burned` | 2450 |
| `calorie_balance` | 0 (ניטרלי) |

### כל שאר הפיצ'רים — defaults מלאים

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

**כל ה-defaults נבחרו להיות "ניטרליים"** — הם לא מושכים את החיזוי לסיכון גבוה או נמוך.

---

## שלב 5 — הפיצ'רים הסופיים (34) לפי סדר חשיבות

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
| 17 | `floors_climbed` | **1.5%** | `daily_health.floorsClimbed` | ישיר |
| 18 | `elevation_gained_m` | **1.5%** | `daily_health.elevationGainedMeters` | ישיר |
| 19 | `respiratory_rate` | **1.5%** | `daily_health.respiratoryRate` | ישיר |
| 20 | `avg_power` | **1.5%** | `daily_health.avgPower` | ישיר |
| 21 | `sleep_hours_ma7` | **1.5%** | היסטוריה 7 ימים | mean(sleep_7d) |
| 22 | `body_fat_pct` | **1.4%** | `daily_health.bodyFatPct` | ישיר |
| 23 | `calorie_balance` | **1.4%** | חישוב | daily_calories − total_burned |
| 24 | `vo2_max` | **1.4%** | `daily_health.vo2Max` | ישיר |
| 25 | `hrv_score` | **1.4%** | `daily_health.hrvRmssd` | ישיר |
| 26 | `nutrition_intake_calories` | **1.4%** | `daily_nutrition.totalCalories` | ישיר / חישוב ממאקרו |
| 27 | `total_calories_burned` | **1.4%** | `daily_health.totalCalories` | ישיר / BMR + active |
| 28 | `spo2` | **1.4%** | `daily_health.oxygenSaturation` | ישיר |
| 29 | `daily_calories` | **1.4%** | `daily_nutrition` | ישיר / חישוב |
| 30 | `max_speed` | **1.4%** | `daily_health.maxSpeed` | ישיר / fallback |
| 31 | `bmi` | **1.4%** | `daily_health.weightKg` + `heightCm` | weight / height² |
| 32 | `age` | **1.4%** | `users/{uid}.age` | ישיר |
| 33 | `speed_intensity_ratio` | **1.4%** | חישוב | max_speed / (avg_speed + 0.1) |
| 34 | `avg_speed` | **1.4%** | `daily_health.avgSpeed` | ישיר / fallback |

**Top 7** (חוסמים ~54.9% מהחשיבות):
`hrv_drop`, `stress_level`, `load_recovery_imbalance`, `injured_yesterday`, `acwr_ratio`, `history_injury_count`, `sleep_debt_3d`

---

## תרשים זרימה מסכם

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
│                                                                   │
│  • המרות יחידות (דקות→שעות, מטרים→קמ)                           │
│  • המרות סקאלה (0-100→1-10)                                      │
│  • Fallbacks (אם חסר → שימוש באתמול / ברירת מחדל)               │
│  • חישוב BMI מגובה+משקל                                          │
│  • הערכת workout_intensity                                        │
│  • חישוב load_recovery_imbalance, speed_intensity_ratio          │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│              FEATURE ENGINEERING (היסטוריה 7 ימים)               │
│                                                                   │
│  confidence = high (7 ימים) / medium (4-6) / low (0-3)          │
│                                                                   │
│  חלון 7 ימים:                                                    │
│  • acute_load_7d = mean(distance, 7d)                            │
│  • chronic_load_21d = אומדן מ-7 ימים                             │
│  • acwr_ratio = acute / chronic                                   │
│  • acwr_ratio_ma7 = mean(acwr, 7d)                               │
│  • sleep_hours_ma7 = mean(sleep, 7d)                             │
│  • hrv_drop = hrv_today − mean(hrv, 7d)                         │
│                                                                   │
│  חלון 3 ימים:                                                    │
│  • sleep_debt_3d = sum(max(0, 8−sleep), 3d)                      │
│                                                                   │
│  confidence=low? → כל הנ"ל מקבלים ערכי ברירת מחדל ניטרליים       │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                  XGBoostDeep MODEL                                │
│                                                                   │
│          34 פיצ'רים → predict_proba → סיכון 0.0–1.0             │
│                                                                   │
│          ≥ 0.18 → High Risk                                      │
│          ≥ 0.11 → Medium Risk                                    │
│          < 0.11 → Low Risk                                       │
└─────────────────────────────────────────────────────────────────┘
```
