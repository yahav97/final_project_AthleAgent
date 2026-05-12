# זרימת נתונים ופיצ'רים — מודל חיזוי פציעות AthleAgent

## סקירה כללית

| פרט | ערך |
|---|---|
| **מודל** | XGBoostRaw |
| **מספר פיצ'רים סופי** | 34 |
| **סף החלטה** | 0.30 |
| **Recall** | 90.3% |
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

### חישוב `workout_intensity_minutes` (נגזר, לא מהשעון)

```
workout_intensity = daily_distance_km × 5.5 + active_calories / 40
```

חסום 0–240 דקות. **לא מגיע ישירות מ-Health Connect**.

### חישוב `calorie_balance` (נגזר)

```
calorie_balance = daily_calories − total_calories_burned
```

### חישוב `avg_speed` / `max_speed` (fallback)

- אם יש מהשעון → שימוש ישיר
- אם אין → `avg_speed = daily_distance_km / (workout_intensity / 60)`
- `max_speed = avg_speed × 1.3`

### חישוב `avg_cadence` (fallback)

- אם יש מהשעון → שימוש ישיר
- אם אין → `steps / workout_intensity_minutes`

---

## שלב 3 — פיצ'רים נגזרים מהיסטוריה (7 ימים)

אלה הפיצ'רים שמחושבים מ-7 ימי `daily_health` שנמשכים מפיירבייס:

| פיצ'ר | מה מחשב | נתון בסיס | חלון |
|---|---|---|---|
| `acute_load_7d` | ממוצע מרחק ב-7 ימים אחרונים | `daily_distance_km` | 7 ימים |
| `chronic_load_21d` | **קירוב** של בסיס כרוני: `weekly_mean × 0.85 + weekly_std × 0.35 + 0.5` | `daily_distance_km` | 7 ימים (אומדן) |
| `acwr_ratio` | `acute_load_7d / chronic_load_21d` חסום 0.35–2.8 | מחושב | — |
| `sleep_debt_3d` | סכום חוב שינה (8 − sleep) ב-3 ימים אחרונים | `sleep_hours` | 3 ימים |
| `hrv_drop` | HRV היום − ממוצע HRV של 7 ימים, חסום ±15 | `hrv_score` | 7 ימים |
| `acwr_ratio_ma7` | כשיש היסטוריה: ממוצע ACWR על 7 ימים. כשאין: = `acwr_ratio` היום | `acwr_ratio` | 7 ימים |
| `sleep_hours_ma7` | כשיש היסטוריה: ממוצע שינה 7 ימים. כשאין: = `sleep_hours` היום | `sleep_hours` | 7 ימים |

### מדיניות confidence (כמה ימים צריך?)

| ימי היסטוריה זמינים | רמת ביטחון | מה קורה |
|---|---|---|
| 7 ימים | **high** | משתמש בפיצ'רים מחושבים מהיסטוריה |
| 4–6 ימים | **medium** | משתמש בפיצ'רים מחושבים (מבוססי rolling עם `min_periods=1`) |
| 0–3 ימים | **low** | ערכי ברירת מחדל קבועים (defaults) לכל פיצ'רי ההיסטוריה |

---

## שלב 4 — הפיצ'רים הסופיים שנכנסים למודל (36)

### לפי סדר חשיבות (Gain)

| # | פיצ'ר | חשיבות | מקור הנתון | חישוב |
|---|---|---|---|---|
| 1 | `stress_level` | **25.4%** | `daily_checkins.stressLevel` | המרת סקאלה |
| 2 | `injured_yesterday` | **22.9%** | `daily_health.injuredYesterday` | bool → 0/1 |
| 3 | `hrv_drop` | **5.8%** | היסטוריה 7 ימים של `hrvRmssd` | HRV_today − mean(HRV_7d) |
| 4 | `acwr_ratio` | **3.7%** | היסטוריה 7 ימים של `distanceMeters` | acute_7d / chronic_estimate |
| 5 | `sleep_debt_3d` | **3.7%** | היסטוריה 3 ימים של `sleepMinutes` | sum(max(0, 8 − sleep)) |
| 6 | `muscle_soreness` | **3.5%** | `daily_checkins.muscleSoreness` | המרת סקאלה (1–5 → 1–10) |
| 7 | `daily_distance_km` | **3.2%** | `daily_health.distanceMeters` | מטרים / 1000 |
| 8 | `sleep_hours` | **2.7%** | `daily_health.sleepMinutes` | דקות / 60 |
| 9 | `history_injury_count` | **2.5%** | `users/{uid}.historyInjuryCount` | ישיר |
| 10 | `workout_intensity_minutes` | **2.1%** | חישוב | distance × 5.5 + calories / 40 |
| 11 | `active_calories_burned` | **1.8%** | `daily_health.activeCalories` | ישיר |
| 12 | `chronic_load_21d` | **1.3%** | היסטוריה 7 ימים | אומדן כרוני מ-7 ימים |
| 13 | `acute_load_7d` | **1.2%** | היסטוריה 7 ימים של `distanceMeters` | mean(distance_7d) |
| 14 | `floors_climbed` | **1.2%** | `daily_health.floorsClimbed` | ישיר |
| 15 | `elevation_gained_m` | **1.0%** | `daily_health.elevationGainedMeters` | ישיר |
| 16 | `sleep_hours_ma7` | **0.9%** | היסטוריה 7 ימים | mean(sleep_7d) |
| 17 | `spo2` | **0.9%** | `daily_health.oxygenSaturation` | ישיר |
| 18 | `energy_level` | **0.9%** | `daily_checkins.energyLevel` | המרת סקאלה |
| 19 | `total_calories_burned` | **0.9%** | `daily_health.totalCalories` | ישיר (או BMR + active) |
| 20 | `respiratory_rate` | **0.9%** | `daily_health.respiratoryRate` | ישיר |
| 21 | `vo2_max` | **0.9%** | `daily_health.vo2Max` | ישיר |
| 22 | `acwr_ratio_ma7` | **0.9%** | היסטוריה / proxy | ממוצע ACWR 7 ימים או = acwr היום |
| 23 | `nutrition_intake_calories` | **0.9%** | `daily_nutrition.totalCalories` | ישיר (או חישוב ממאקרו) |
| 24 | `daily_calories` | **0.9%** | `daily_nutrition` | ישיר או חישוב |
| 25 | `avg_power` | **0.9%** | `daily_health.avgPower` | ישיר (0 אם אין מד כוח) |
| 26 | `bmi` | **0.9%** | `daily_health.weightKg` + `heightCm` | weight / height² |
| 27 | `hrv_score` | **0.9%** | `daily_health.hrvRmssd` | ישיר (חסום 30–105) |
| 28 | `calorie_balance` | **0.8%** | חישוב | daily_calories − total_burned |
| 29 | `avg_speed` | **0.8%** | `daily_health.avgSpeed` | ישיר / fallback |
| 30 | `age` | **0.8%** | `users/{uid}.age` | ישיר |
| 31 | `max_speed` | **0.8%** | `daily_health.maxSpeed` | ישיר / fallback |
| 32 | `body_fat_pct` | **0.8%** | `daily_health.bodyFatPct` | ישיר |
| 33 | `resting_hr` | **0.8%** | `daily_health.restingHeartRate` | ישיר (fallback מ-min/avg) |
| 34 | `avg_cadence` | **0.8%** | `daily_health.avgCadence` | ישיר / fallback |

---

## תרשים זרימה מסכם

```
┌─────────────────────────────────────────────────────────────────┐
│                        FIREBASE                                  │
├──────────────┬──────────────┬───────────────┬──────────────────-─┤
│ users/{uid}  │ daily_health │ daily_checkins│ daily_nutrition    │
│              │ (7 ימים)     │ (היום)        │ (היום + fallback)  │
│ • age        │ • sleep      │ • stress      │ • calories         │
│ • injuries   │ • distance   │ • soreness    │ • protein          │
│              │ • HR/HRV     │ • energy      │ • carbs            │
│              │ • calories   │               │                    │
│              │ • speed/power│               │                    │
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
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│              FEATURE ENGINEERING (היסטוריה)                       │
│                                                                   │
│  חלון 7 ימים:                                                    │
│  • acute_load_7d = mean(distance, 7 days)                        │
│  • chronic_load_21d = אומדן מ-7 ימים                             │
│  • acwr_ratio = acute / chronic                                   │
│  • acwr_ratio_ma7 = mean(acwr, 7 days)                           │
│  • sleep_hours_ma7 = mean(sleep, 7 days)                         │
│                                                                   │
│  חלון 3 ימים:                                                    │
│  • sleep_debt_3d = sum(max(0, 8−sleep), 3 days)                  │
│                                                                   │
│  חלון 7 ימים + היום:                                             │
│  • hrv_drop = hrv_today − mean(hrv, 7 days)                     │
│                                                                   │
│  (הוסרו: acwr_ratio_std21, sleep_hours_std21 — לא נדרשים)        │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    XGBoost MODEL                                  │
│                                                                   │
│          34 פיצ'רים → predict_proba → סיכון 0.0–1.0             │
│                                                                   │
│          סף: 0.30 → High Risk                                    │
│          סף: 0.18 → Medium Risk                                  │
│          מתחת    → Low Risk                                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## חשיבות פיצ'רים — איך נקבעה?

### שיטה: Gain (XGBoost)

XGBoost מחשב את ה-**Gain** — השיפור ב-Loss Function שהושג בכל פיצול (split) בעצים. הפיצ'ר שנותן את הפיצולים הכי "מרוויחים" מקבל חשיבות גבוהה יותר.

- **לא נקבע ידנית** — המודל מגלה לבד מה חשוב
- סכום כל החשיבויות = 100%
- 260 עצים, כל אחד עם עומק מקסימלי 5 → אלפי פיצולים שמתמצתים לטבלת חשיבות

### למה stress ו-injured_yesterday כל כך דומיננטיים?

| פיצ'ר | חשיבות | סיבה |
|---|---|---|
| `stress_level` | 25.4% | מסכם את המצב הכולל: קורלטיבי ל-HRV, שינה, עייפות. פיצול יחיד מפריד טוב |
| `injured_yesterday` | 22.9% | סיגנל בינארי חד — אחרי פציעה ההסתברות לפציעה נוספת עולה דרמטית |
| **יחד** | **48.3%** | כמעט חצי מהמידע שהמודל צריך |

### Top 5 = 61.5% מהחשיבות

`stress_level` + `injured_yesterday` + `hrv_drop` + `acwr_ratio` + `sleep_debt_3d`

---

## ערכי ברירת מחדל (כשנתון חסר)

| פיצ'ר | Default | משמעות |
|---|---|---|
| `sleep_hours` | 7.0 | שינה "ממוצעת" |
| `stress_level` | 5.0 | סטרס ניטרלי |
| `muscle_soreness` | 5.0 | כאב ניטרלי |
| `acwr_ratio` | 1.0 | עומס מאוזן |
| `hrv_drop` | 0.0 | אין שינוי ב-HRV |
| `sleep_debt_3d` | 1.0 | חוב שינה מינימלי |
| `injured_yesterday` | 0.0 | לא נפצע |

ערכי ברירת המחדל נבחרו כ-"ניטרליים" — הם לא מושכים את החיזוי לכיוון סיכון גבוה או נמוך.
