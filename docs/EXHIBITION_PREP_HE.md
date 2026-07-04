# AthleAgent — מדריך הכנה לתערוכה

> **מטרה:** להכין אותך להציג את הפוסטר ולענות לעומק על כל מה שכתוב בו — וגם על שאלות שמחוץ לפוסטר.  
> **עקרון מספרים:** בפני הקהל — **הפוסטר הוא מקור האמת**. הערות שוליים בסוף המסמך מסבירות עדכונים בקוד (אם שואלים).

| שדה | ערך |
|-----|-----|
| **מגישים** | יהב סימון, צוף פלדון |
| **מנחה** | מר איל איזנשטיין \| מדעי המחשב |
| **מסמכים קשורים** | [HLD_PROJECT.md](HLD_PROJECT.md) · [EXHIBITION_QA_CHEATSHEET_HE.md](EXHIBITION_QA_CHEATSHEET_HE.md) · [RISK_SCORE.md](../backend/docs/RISK_SCORE.md) · [LLD.md](../backend/docs/LLD.md) |

---

## ✅ צ'קליסט לפני תערוכה (שלב 1)

הרץ **לפני** הדמו החי:

| # | בדיקה | פקודה / מיקום | תוצאה צפויה |
|---|--------|---------------|-------------|
| 1 | מודל promoted זמין | `cd backend && python -m pytest tests/unit/test_model_loader.py::TestPromotedArtifactReadiness -q` | `1 passed` |
| 2 | Backend רץ (Docker) | `docker compose up --build` | `/status/ml` → `"status": "Live"` |
| 3 | Backend לא חשוף לרשת | `docker-compose.yml` → `127.0.0.1:8000:8000` | נגיש רק מ-localhost / emulator |
| 4 | Firebase key | `backend/firebase-key.json` קיים | אין שגיאת credentials |
| 5 | Android מחובר | Emulator → `10.0.2.2:8000` | check-in מפעיל ML |

**מספרים לשאלות על המודל (מ-manifest, לא מהפוסטר):** XGBoostCalibratedTuned @ 0.10 · Recall **81.1%** · ROC-AUC **79.3%** · run `20260629_184034`.

---

## חלק א׳ — פתיחה (30 שניות)

### Elevator pitch

> **AthleAgent** היא פלטפורמה למניעת פציעות בספורטאים. במקום לטפל בפציעה **אחרי** שהיא קרתה, המערכת מחשבת כל בוקר **ציון סיכון יומי** (0–100%) שמאחד עומס אימון, שינה, תזונה ומצב נפשי — ומציגה אותו לספורטאי ולמאמן.

**משפט מפתח:** *מעבר מטיפול תגובתי בפציעות ל**מניעה**.*

### שני סוגי משתמשים

| תפקיד | מה עושה | מסך מרכזי |
|-------|---------|-----------|
| **ספורטאי** | מסנכרן שעון, ממלא סקר, (אופציונלי) מצלם ארוחה | `AthleteDashboardActivity` — מחוון סיכון + גרף + המלצת Gemini |
| **מאמן** | יוצר קבוצה, מאשר בקשות הצטרפות | `CoachDashboardActivity` — רשימת ספורטאים + סיכון לכל אחד |

### Tagline מהפוסטר

**"פלטפורמה אחודה מבוססת ML: איסוף נתונים יומי המזין דאשבורד למאמנים ולספורטאים לניהול סיכונים והערכת סיכון לפציעה."**

**מה זה אומר בפועל:**
- **אחודה** — כל המקורות (שעון, סקר, תזונה) נכנסים לציון אחד, לא לאפליקציות נפרדות.
- **יומי** — החיזוי הוא ל**היום** (בוקר האימון), לא תחזית לשבוע הבא.
- **דאשבורד** — לא רק מספר; גם רמת סיכון (נמוך/בינוני/גבוה), היסטוריה, והמלצות טקסט.

---

## חלק ב׳ — פירוק הפוסטר שורה-שורה

### כותרת ונקודות מרכזיות (מעל הסעיפים)

#### אינטגרציה מרובת מקורות: 21 מדדים פיזיים + תזונה + סקר מנטלי

| מקור | מה נאסף | איפה נשמר | קובץ בקוד |
|------|---------|-----------|-----------|
| **Health Connect** (שעון חכם) | שינה, צעדים, מרחק, דופק, HRV, VO2, SpO2, קלוריות, גובה, קומות, קצב, מהירות, כוח ועוד | `users/{uid}/daily_health/{date}` | `WearableSyncActivity.kt` |
| **סקר מנטלי יומי** | אנרגיה, כאב שרירים, סטרס (1–10), פציעה אתמול | `users/{uid}/daily_checkins/{date}` | `DailyCheckInActivity.kt` |
| **תזונה (AI)** | קלוריות, חלבון, פחמימות מתמונת ארוחה | `users/{uid}/daily_nutrition/{date}` | `AnalyzingMealActivity.kt` + Gemini Vision |

**למה "21 מדדים פיזיים"?**  
ב-Health Connect מוגדרים **19 סוגי רשומות** (הרשאות קריאה): שינה, דופק, צעדים, מרחק, מהירות, קלוריות פעילות/כוללות, BMR, משקל, HRV, דופק מנוחה, SpO2, VO2max, אחוז שומן, קצב נשימה, עליית גובה, קומות, קצב צעדים, סשן אימון. מהן נגזרים שדות נוספים ב-Firestore (למשל `sleepMinutes`, `distanceMeters`, `heartRateAvg`). המספר 21 בפוסטר מתאר את **מקורות האיסוף הפיזיים** — לא את מספר הפיצ'רים של המודל.

**חשוב להבחין:** המודל ML משתמש ב-**35 פיצ'רים** (כולל פיצ'רים מחושבים כמו ACWR, חוב שינה, ירידת HRV). **15 מהם** מוגדרים כמספרים שלמים ב-`integer_feature_columns`. ראו [model_feature_contract.json](../backend/data/model_feature_contract.json).

---

#### חיזוי סיכון יומי: XGBoost → 3 רמות

| שלב | מה קורה | מודול בקוד |
|-----|---------|------------|
| 1 | קריאת snapshot מ-Firestore + חלון 7 ימי היסטוריה | `history/repository.py` |
| 2 | מיזוג שדות (שינה@D, עומס@D-1) + תזונה + סקר | `prediction/firestore_mapping.py` |
| 3 | מילוי תזונה חסרה בממוצע אוכלוסייה (אם צריך) | `nutrition_defaults.resolve_request_nutrition` |
| 4 | מיפוי request → 35 פיצ'רים + ACWR / חוב שינה | `preprocessing/request_features.py`, `feature_engineering.py` |
| 5 | העשרת פיצ'רים היסטוריים (או defaults אם היסטוריה דלה) | `prediction/confidence.apply_history_confidence_fallback` |
| 6 | `predict_proba` → הסתברות פציעה **היום** (0–1) | `prediction/service.py` + joblib bundle |
| 7 | סיווג רמה + חישוב `prediction_confidence` | `risk_levels.py`, `compute_prediction_confidence_percent` |
| 8 | כתיבה ל-Firestore: `finalRiskScore`, `riskLevel` | `history/repository.save_daily_prediction_result` |

**רמות סיכון (production):**

| רמה | טווח `finalRiskScore` | צבע ב-UI |
|-----|----------------------|----------|
| **Low** (נמוך) | 0–20% | ירוק |
| **Medium** (בינוני) | 21–70% | צהוב/כתום |
| **High** (גבוה) | 71–100% | אדום |

קוד: `backend/services/risk_levels.py`

**למה XGBoost?**  
Gradient boosting על עצי החלטה — מתאים לטאבלארי, מטפל ביחסים לא-ליניאריים (למשל ACWR גבוה + שינה נמוכה יחד), ונותן feature importance לניתוח.

---

#### ביצועי המודל (כפי שמופיע בפוסטר)

| מדד בפוסטר | משמעות | איך להסביר לקהל |
|------------|--------|-----------------|
| **340,000 רשומות** | שורות אימון סינתטיות (1,000 ספורטאים × 340 ימים) | "אימנו על כ-340 ימים לכל אחד מ-1,000 ספורטאים וירטואליים" |
| **Recall 86.6%** | מתוך כל הימים עם פציעה אמיתית — כמה תפסנו | "רוב מקרי הסיכון הגבוה לא מפספסים — קריטי למניעה" |
| **ROC-AUC 0.72** | יכולת הפרדה כללית בין יום עם/בלי פציעה | "0.5 = מטבע, 1.0 = מושלם; 0.72 = הפרדה סבירה" |
| **Brier-Score 0.115** | כיול הסתברויות — נמוך יותר = טוב יותר | "כשהמודל אומר 30% — באמת בערך שליש מהמקרים נפצעים" |

**מאיפה הדאטה?**  
`ML_model/data_generator.py` — דאטה **סינתטי** עם מודל סיכון מבוסס מחקר ספורט:

- **ACWR > 1.4** — יחס עומס חד לכרוני (Gabbett, 2016)
- **חוב שינה** מצטבר
- **ירידת HRV** — לחץ על מערכת העצבים האוטונומית
- **סטרס גבוה** + עומס — אפקט מכפיל
- **Cooldown** אחרי פציעה

Pipeline: `data_generator.py` → `create_benchmark_set.py` → `train_model.py` (CV×2 → 5 מועמדים → benchmark holdout → refit מלא) → `run_pipeline.py` → `artifacts/promoted.json`

פרוטוקול מלא: [`ML_model/docs/MODEL_SELECTION.md`](../ML_model/docs/MODEL_SELECTION.md)

---

### סעיף 1 — תיאור הבעיה

#### נתונים מפוזרים

**הבעיה:** ספורטאי מנהל עומס ב-Garmin/Strava, תזונה ב-MyFitnessPal, שינה באפליקציה נפרדת. המאמן רואה רק חלק מהתמונה.

**הפתרון שלנו:** מקור אמת אחד — **Cloud Firestore** — שמאגד הכל לפני חיזוי.

#### גישה תגובתית

**הבעיה:** רוב המערכות בתעשייה מתמקדות ב**שיקום** — פיזיותרפיה, MRI, הפסקת אימונים — **אחרי** שהפציעה כבר קרתה.

**הפתרון שלנו:** **מניעה** — התראה מוקדמת כשדפוסי הסיכון (עומס + שחיקה + שינה גרועה) מצטברים.

#### מורכבות חישוב

**הבעיה:** מדדים כמו **ACWR** (Acute:Chronic Workload Ratio), **חוב שינה 3 ימים**, **ירידת HRV** — קשים לחשב ידנית ב-5 דקות בבוקר לפני אימון.

**הפתרון שלנו:** המודל מחשב **35 פיצ'רים** אוטומטית, כולל rolling features על 7 ימים אחורה.

#### הצורך

**הבעיה:** אין כלי שמעריך **סיכון פציעה יומי** באופן אוטומטי ממקורות מרובים.

**הפתרון שלנו:** פלטפורמה מבוססת ML שמייצרת **Daily Injury Risk Score** כל בוקר.

---

### סעיף 2 — פתרון (ארכיטקטורה)

```mermaid
sequenceDiagram
    participant App as Android
    participant FS as Firestore
    participant BE as FastAPI
    participant ML as XGBoost

    App->>FS: כתיבת נתונים יומיים
    App->>BE: POST /predict/daily
    BE->>FS: קריאת snapshot + 7 ימים
    BE->>ML: predict_proba
    BE->>FS: finalRiskScore, riskLevel
    App->>FS: קריאת תוצאה לדשבורד
```

#### שכבת הלקוח — Android/Kotlin

| נושא | מה לומר |
|------|---------|
| **טכנולוגיה** | Kotlin native, Activities, View Binding, Material Design, Retrofit |
| **Health Connect** | גשר סטנדרטי של Google לשעונים (Garmin, Samsung, Pixel Watch וכו') |
| **Gemini Vision** | ניתוח ארוחה מתמונה — **בלי הקלדה ידנית** של קלוריות |
| **שני תפקידים** | routing אחרי Firebase Auth — ספורטאי או מאמן |

**הערה פנימית (אם שואלים על MVVM):**  
הפוסטר מציין "ארכיטקטורת MVVM". **במימוש בפועל** — Activity-centric + View Binding, **ללא** ViewModel/Repository (ראו [README.md](../README.md)). ניסוח מומלץ: *"תכננו הפרדת שכבות; בפרויקט הגמר יישמנו Activities ישירות לצמצום scope — עם roadmap ל-Repository layer."*

#### בסיס הנתונים — Firebase

| רכיב | תפקיד |
|------|-------|
| **Firebase Auth** | התחברות (אימייל + Google), routing לפי role |
| **Cloud Firestore** | **מקור אמת ל-UI** — כל הנתונים היומיים + תוצאות חיזוי |

**עקרון מרכזי — Firestore-as-truth:**
1. האפליקציה **כותבת** נתונים ל-Firestore
2. האפליקציה **מפעילה** `POST /predict/daily` (trigger בלבד)
3. הבקאנד **קורא** מ-Firestore, מריץ ML, **כותב חזרה** `finalRiskScore`
4. האפליקציה **קוראת** את התוצאה מ-Firestore לדשבורד — **לא** מה-response body של ה-API

#### שכבת השרת — FastAPI/Python

| endpoint | תפקיד |
|----------|-------|
| `POST /predict/daily` | חיזוי production — body: `{userId, date}` |
| `GET /status/ml` | האם המודל Live או Blocked |
| `GET /health` | liveness |
| `POST /api/v1/observability/client-events` | telemetry מהאנדרואיד |

**מה קורה בחיזוי (צינור מפורט):**

```
POST /predict/daily { userId, date }
  → fetch_daily_firestore_snapshot
  → injury_prediction_request_from_firestore_snapshot
  → resolve_request_nutrition
  → base_model_features_from_request + compute_derived_features
  → injury_request_to_model_dataframe (35 עמודות)
  → apply_history_confidence_fallback (7 ימים, HistoryConfidence)
  → calculate_data_quality_score (weak_fields)
  → compute_prediction_confidence_percent
  → resolve_model_bundle → validate_feature_vector_for_model
  → predict_proba → classify_risk_level
  → save_daily_prediction_result
```

**בשורה אחת לקהל:** קוראים את מה שנשמר ב-Firestore, בונים 35 מספרים שהמודל מכיר, מריצים XGBoost, ושומרים חזרה ציון + רמת סיכון + confidence.

#### בקרת אמינות ושלמות נתונים

הפוסטר: *"מנגנון אימות קלט המונע מתן ציון סיכון במצב של נתונים חסרים"*.

**בפועל — שכבות הגנה:**

| מנגנון | מה עושה |
|--------|---------|
| **Cross-trigger** | חיזוי רק כשגם סקר **וגם** סנכרון שעון הושלמו |
| **prediction_confidence** | מספר 0–100 נפרד מהסיכון — "כמה הקלט אמין" (ראו למטה) |
| **Defaults ניטרליים** | שדות חסרים לא מניחים 0 שינה (= סיכון נמוך מלאכותי) |
| **ML manifest gates** | אם Recall < 80% או AUC < 0.68 — הבקאנד מחזיר **HTTP 503** ולא משרת חיזוי |
| **nutritionImputed** | תזונה חסרה → ממוצעים מ-`config.NUTRITION_DEFAULT_*` + קנס ב-quality score |

#### `prediction_confidence` — איך מחשבים? (לשאלות עומק)

המודל **תמיד** מחזיר סיכון. ה-confidence אומר **כמה לסמוך על הקלט** — לא משנה את הסיכון.

**נוסחה** (`backend/config.py` + `prediction/confidence.py`):

```
prediction_confidence = (0.6 × history_score + 0.4 × quality_score) × 100
```

| רכיב | משקל | מה נמדד |
|------|------|---------|
| **history_score** | 60% | כמה "ימי שעון אמיתיים" יש ב-7 הימים האחרונים |
| **quality_score** | 40% | שלמות שדות הבוקר (שינה, צעדים, HRV...) — 0 עד 1 |

**יום איכותי בהיסטוריה** (`history/day_quality.py`): בשורה ממוזגת (עומס@אתמול + שינה@היום) צריך לפחות **3 מתוך 4** קטגוריות עם ערך תקין:

| קטגוריה | דוגמאות שדות |
|---------|--------------|
| עומס (load) | `steps`, `distanceMeters` |
| שינה (sleep) | `sleepMinutes` |
| דופק (heart) | `heartRateAvg`, `hrvRmssd`, `restingHeartRate` |
| אנרגיה (energy) | `activeCalories`, `totalCalories`, `bmrCalories` |

| ימי איכות בחלון 7 | רמת היסטוריה | `history_score` |
|-------------------|--------------|-----------------|
| ≥ 7 | HIGH | 0.95 |
| 4–6 | MEDIUM | 0.70 |
| 0–3 | LOW | 0.45 |

**quality_score** (`preprocessing/quality.py`): מתחיל מ-1.0, יורד **−0.08** לכל שדה מדידה חסר/אפס (`SAME_DAY_MEASUREMENT_FIELDS`), **−0.12** אם תזונה ממוצעת (`nutritionImputed`) או גיל ברירת מחדל (`ageImputed`, `PROFILE_DEFAULT_AGE=22`).

**דוגמה מספרית:** היסטוריה HIGH (0.95) + קלט חלקי (0.8) → `(0.6×0.95 + 0.4×0.8)×100 ≈ 89`.

**משפט לתערוכה:** *"הסיכון הוא תחזית המודל; ה-confidence אומר כמה הנתונים של הבוקר והשבוע אמינים."*

**Cross-trigger בפירוט:**

| מסך | מפעיל חיזוי כאשר |
|-----|------------------|
| `DailyCheckInActivity` | `sleepMinutes` קיים ב-`daily_health/{היום}` |
| `WearableSyncActivity` | `energyLevel` קיים ב-`daily_checkins/{היום}` |

`MealAnalysisActivity` **לא** מפעיל חיזוי — רק שומר תזונה.

---

### סעיף 3 — ארכיטקטורה (אתגרים)

#### אמינות החיזוי תחת מידע חסר

**האתגר:** משתמש לא תמיד מסנכרן שעון, מפספס סקר, או שאין תזונה.

**הפתרון:**
- **`prediction_confidence`** (0–100) — **לא** סיכון פציעה! שילוב של:
  - **60%** — עומק היסטוריית שעון (ימי איכות בחלון 7)
  - **40%** — שלמות שדות הבוקר (`quality_score`)
- **השלמה ניטרלית** — ערכי default שלא מוטים לכיוון סיכון גבוה או נמוך; תזונה חסרה → ממוצע אוכלוסייה מסומן `nutritionImputed`.
- **התניית חיזוי** — cross-trigger: לא מריצים ML בלי שינה **וגם** סקר.

**דוגמה לקהל:**  
"אם המודל אומר 45% סיכון אבל confidence רק 30 — אנחנו מציגים את הסיכון אבל יודעים שהקלט חלקי."

#### פער נתונים בשעת החיזוי

**האתגר:** בבוקר יום D עדיין **אין** נתוני אימון של היום — רק שינה מהלילה וסקר.

**הפתרון — מדיניות date-split:**

| נתון | תאריך במסמך Firestore | למה |
|------|----------------------|-----|
| שינה | `daily_health/{D}` | הלילה שזה עתה נגמר |
| עומס פיזי (צעדים, מרחק, HRV...) | `daily_health/{D-1}` | יום מלא אתמול |
| סקר | `daily_checkins/{D}` | מצב נפשי הבוקר |
| תזונה | `daily_nutrition/{D-1}` | צריכה אתמול |
| Rolling (ACWR, חוב שינה) | 7 ימים עד **D-1** | היסטוריה לפני היום |

**למה זה נכון מבחינה מדעית:** בבוקר האימון המאמן שואל "מה הסיכון **היום**?" — התשובה מבוססת על מה שכבר קרה (אתמול + הלילה), לא על עומס שעדיין לא נאסף.

#### היעדר נתוני שטח אמיתיים ומתויגים

**האתגר:** אין מספיק דאטה אמיתי עם תיוג "נפצע / לא נפצע" לכל יום.

**הפתרון:**
- `data_generator.py` — 1,000 ספורטאים × 340 יום (= 340,000 שורות), hazard model מבוסס מחקר
- תיוג: `injury_today` — פציעה ביום D

---

### סעיף 4 — אתגר הנדסי (כותרת בלבד בפוסטר)

הפוסטר מציג כותרת **"4. אתגר הנדסי"** ללא טקסט. **המלצה:** כשמצביעים על הסעיף — לדבר על 2–3 נקודות הבאות (מתוך סעיף 3 + מעבר):

| אתגר | הסבר קצר |
|------|----------|
| **Train-serve parity** | אותן נוסחאות + **אותם סוגי ערכים** (15 עמודות שלמות) — חוזה `model_feature_contract.json`, `feature_contract.py` (אימון), `coerce_whole_number_features()` (שרת) |
| **Model manifest gates** | הבקאנד לא משרת מודל גרוע — `GET /status/ml` → Live/Blocked (`config.ML_MIN_*`) |
| **Firestore-as-truth** | decoupling: trigger חיזוי ≠ קריאת תוצאה — תומך retry ו-async |
| **Date-split sync** | שינה ל-{D}, עומס ל-{D-1} — `firestore_mapping.py` + `WearableSyncActivity` |
| **Observability** | `X-Request-ID` מ-Android ל-`logs/athleagent.log` — trace מקצה לקצה בלי PHI |
| **קריאות קוד** | מודולים קטנים עם שמות מפורשים (`ResolvedModelBundle`, `SAME_DAY_MEASUREMENT_FIELDS`) — קל להסביר בבחינה |

---

## חלק ג׳ — מעבר לפוסטר

### מפת מודולי Backend (לשאלות "איפה זה בקוד?")

| תיקייה / קובץ | אחריות |
|---------------|--------|
| `prediction/service.py` | orchestration: nutrition → features → ML → תשובה |
| `prediction/firestore_mapping.py` | Firestore snapshot → `InjuryPredictionRequest` |
| `prediction/confidence.py` | היסטוריה 7 ימים + `compute_prediction_confidence_percent` |
| `prediction/bundle.py` | `ResolvedModelBundle` — parse של joblib |
| `preprocessing/request_features.py` | API fields → שמות מודל |
| `preprocessing/quality.py` | `quality_score`, `weak_fields` |
| `history/day_quality.py` | יום איכותי = 3/4 קטגוריות שעון |
| `history/rolling_features.py` | ACWR, sleep_debt, hrv_drop על היסטוריה |
| `config.py` | כל הספים: risk, history, confidence, nutrition |
| `data/model_feature_contract.json` | 35 עמודות + `integer_feature_columns` + defaults |

### קבועי מדיניות מרכזיים (`backend/config.py`)

| קבוע | ערך (ברירת מחדל) | שימוש |
|------|------------------|-------|
| `RISK_HIGH_CUTOFF` | 0.70 | מעל → High (71–100%) |
| `RISK_MEDIUM_CUTOFF` | 0.20 | מעל → Medium (21–70%) |
| `HISTORY_LOOKBACK_DAYS` | 7 | חלון rolling features |
| `HISTORY_CONFIDENCE_HIGH_MIN_DAYS` | 7 | היסטוריה חזקה |
| `HISTORY_CONFIDENCE_MEDIUM_MIN_DAYS` | 4 | היסטוריה בינונית |
| `HISTORY_MIN_WATCH_SYNC_SIGNAL_GROUPS` | 3 | מינימום קטגוריות ליום איכותי |
| `CONFIDENCE_HISTORY_WEIGHT` | 0.6 | משקל היסטוריה ב-confidence |
| `CONFIDENCE_QUALITY_WEIGHT` | 0.4 | משקל איכות יום ב-confidence |
| `NUTRITION_DEFAULT_PROTEIN` | 130g | ממוצע כשאין לוג תזונה |

### זרימת נתונים — תמונה כוללת

```mermaid
flowchart LR
    subgraph inputs [מקורות קלט]
        HC[Health Connect]
        Survey[סקר יומי]
        Meal[ארוחה + Gemini]
        Profile[פרופיל]
    end
    subgraph storage [Firestore]
        DH[daily_health]
        DC[daily_checkins]
        DN[daily_nutrition]
    end
    subgraph ml [Backend ML]
        FE[35 features]
        XGB[XGBoost]
        Score[finalRiskScore]
    end
    HC --> DH
    Survey --> DC
    Meal --> DN
    Profile --> FE
    DH --> FE
    DC --> FE
    DN --> FE
    FE --> XGB --> Score
    Score --> DH
```

### זרימת Demo מומלצת (2–3 דקות)

1. **התחברות** כספורטאי (Firebase Auth)
2. **סנכרון Health Connect** — שינה + עומס אתמול
3. **סקר יומי** — אנרגיה, סטרס, כאב שרירים
4. *(אופציונלי)* **צילום ארוחה** → Gemini מחלץ מאקרו
5. **דשבורד ספורטאי** — מחוון סיכון, גרף MPAndroidChart, המלצת Gemini
6. **מעבר למאמן** — דשבורד קבוצתי: סיכון לכל ספורטאי

**דרישות טכניות לפני התערוכה:**

```powershell
# מהשורש של ה-repo
docker compose up --build
# או: cd backend && uvicorn main:app --reload

# וידוא:
# GET http://localhost:8000/status/ml → "status": "Live"
```

- `backend/firebase-key.json` (לא ב-git)
- `google-services.json` באנדרואיד
- `GEMINI_API_KEY` ב-`local.properties`
- מכשיר פיזי עם Health Connect (מומלץ)
- Retrofit מצביע ל-`10.0.2.2:8000` (אמולטור) או IP המחשב (מכשיר)

### 35 הפיצ'רים — רשימה מלאה

```
bmi, age, body_fat_pct, vo2_max, history_injury_count, injured_yesterday,
daily_distance_km, workout_intensity_minutes, avg_cadence, elevation_gained_m,
floors_climbed, avg_speed, max_speed, avg_power, active_calories_burned,
sleep_hours, hrv_score, resting_hr, respiratory_rate, spo2,
nutrition_intake_calories, daily_calories, total_calories_burned,
stress_level, muscle_soreness, energy_level,
acute_load_7d, acwr_ratio, acwr_ratio_ma7, calorie_balance,
sleep_hours_ma7, sleep_debt_3d, hrv_drop, load_recovery_imbalance,
speed_intensity_ratio
```

### Top 5 פיצ'רים לפי חשיבות (מודל promoted)

| פיצ'ר | משמעות | חשיבות |
|-------|--------|--------|
| `hrv_drop` | ירידה ב-HRV לעומת ממוצע 7 ימים | ~28% |
| `stress_level` | סטרס מהסקר היומי | ~14% |
| `sleep_debt_3d` | חוב שינה מצטבר 3 ימים | ~11% |
| `injured_yesterday` | האם נפצע אתמול | ~9% |
| `load_recovery_imbalance` | חוסר איזון בין עומס להתאוששות | ~7% |

### כיול לפי רמות סיכון (holdout, מודל promoted)

| רמת ציון | % דגימות בטווח | שיעור פציעה בפועל |
|----------|----------------|-------------------|
| ירוק (0–20%) | רוב הימים | ~9% |
| צהוב (20–50%) | בינוני | ~31% |
| אדום (50–100%) | מיעוט | ~65% |

→ המודל **מכויל**: כשהציון גבוה, באמת יש יותר פציעות.

### שלושה מספרים שמבלבלים — להבדיל בבירור

| שם | טווח | משמעות |
|----|------|--------|
| `finalRiskScore` | 0–100% | **מה שהמשתמש רואה** — הסתברות פציעה היום |
| `risk_score` | 0–1 | אותו ערך בשרת (לפני הכפלה ב-100) |
| `prediction_confidence` | 0–100 | **איכות הקלט** — לא הסיכון! |

### שאלות "קשות" — תשובות מוכנות

| שאלה | תשובה |
|------|--------|
| **"זה באמת מנבא פציעות?"** | מודל הסתברותי שמזהה דפוסי סיכון מדאטה היסטורי. **לא** אבחון רפואי ולא מחליף איש מקצוע. |
| **"למה Recall גבוה ו-Precision נמוך?"** | במניעה עדיף **להזהיר מוקדם** (false positive) מאשר לפספס פציעה (false negative). Recall גבוה = תופסים רוב המקרים. |
| **"מה אם אין שעון?"** | אפשר חיזוי מסקר + פרופיל, אבל `prediction_confidence` יורד — המערכת "יודעת" שהקלט חלקי. |
| **"איך מגינים על פרטיות?"** | Firebase Auth, הרשאות Health Connect, Gemini רץ בלקוח, אין PHI בלוגים (NFR-SEC-01). |
| **"למה אין auth על API?"** | מגבלת scope בפרויקט גמר. מתועד ב-[HLD_PROJECT.md](HLD_PROJECT.md) §8. Roadmap: Firebase ID Token בבקאנד. |
| **"MVVM?"** | כיוון עיצובי בפוסטר; מימוש Activity-centric. Roadmap: Repository layer. |
| **"מה ההבדל בין סיכון ל-confidence?"** | **סיכון** = מה המודל חוזה (הסתברות פציעה). **Confidence** = כמה הנתונים אמינים (היסטוריה + שלמות בוקר) — לא משנה את הסיכון, רק את מידת האמון. |
| **"מה ההבדל מ-Whoop/Oura?"** | הם מתמקדים בספורטאי בודד; AthleAgent מוסיף **מאמן + קבוצה** + מודל ML משלנו + תזונה מצילום. |
| **"האם הדאטה אמיתי?"** | אימון על דאטה **סינתטי** מבוסס מחקר (ACWR, שינה, HRV). האפליקציה שומרת נתונים אמיתיים ב-Firestore לשימוש בחיזוי. |

### Roadmap (מעבר לפוסטר)

1. Auth על API (Firebase token middleware)
2. Firestore Security Rules מחמירות
3. Deploy בקאנד ל-Cloud Run / Render
4. Repository layer ב-Android
5. Trigger gate בפרונט — בדיקת עומס `{D-1}` לפני חיזוי

### מסמכים לקריאה לפני התערוכה

| מסמך | תוכן |
|------|------|
| [HLD_PROJECT.md](HLD_PROJECT.md) | ארכיטקטורה מלאה בעברית |
| [RISK_SCORE.md](../backend/docs/RISK_SCORE.md) | pipeline ציון סיכון E2E (~1000 שורות) |
| [FEATURES.md](../backend/docs/FEATURES.md) | חוזה Firestore → מודל |
| [LLD.md](../backend/docs/LLD.md) | עיצוב ברמה נמוכה — Backend modules |
| `backend/config.py` | ספי risk / history / confidence / nutrition |
| [NFR.md](NFR.md) | דרישות לא-פונקציונליות מדידות |
| [model_improvement_journey.ipynb](../ML_model/notebooks/model_improvement_journey.ipynb) | מסע שיפור המודל |

---

## הערות שוליים — פערים בין פוסטר לקוד (רק אם שואלים)

> **בפני הקהל:** הציגי את המספרים מהפוסטר. הטבלה הזו לשימוש פנימי בלבד.

| נושא | בפוסטר | בקוד עדכני (promoted `20260629_184034`) |
|------|--------|----------------------------------------|
| Recall | 86.6% | **81.1%** (XGBoostCalibratedTuned @ threshold 0.10) |
| ROC-AUC | 0.72 | **0.793** |
| Brier | 0.115 | **0.113** |
| רשומות | 340,000 | 340,000 (1,000 × 340) |
| מודל | XGBoost (כללי) | **XGBoostCalibratedTuned** (כיול sigmoid) |
| ארכיטקטורה Android | MVVM | **Activity-centric** + View Binding |

**ניסוח מומלץ אם שואלים על עדכון:**

> "המספרים בפוסטר משקפים את מחזור האימון שבו עיצבנו את המערכת. מאז שיפרנו את המודל עם **כיול (calibration)** — ה-AUC עלה לכ-0.79, וה-Recall נשאר **מעל 80%** — זה הסף המינימלי שלנו לשרת חיזוי בפרודקשן."

**למה Recall ירד מ-86.6 ל-81.1?**  
בחירת מודל מכויל (CalibratedTuned) עם threshold נמוך יותר (0.10) — trade-off: Recall עדיין מעל gate (80%), AUC ו-Brier משתפרים, Precision מעט גבוה יותר.

---

## Tech Stack — סיכום לשאלות

| שכבה | טכנולוגיות |
|------|------------|
| **Android** | Kotlin, Activities, View Binding, Retrofit, MPAndroidChart |
| **Cloud** | Firebase Auth, Cloud Firestore |
| **Backend** | Python, FastAPI, Uvicorn, firebase-admin |
| **ML** | XGBoost, scikit-learn, pandas, joblib |
| **AI** | Google Gemini Vision + Text (client-side) |
| **Health** | Google Health Connect SDK |
| **DevOps** | Docker, GitHub Actions (pytest), **214+** בדיקות backend |

---

*בהצלחה בתערוכה! לתרגול מהיר — ראי [EXHIBITION_QA_CHEATSHEET_HE.md](EXHIBITION_QA_CHEATSHEET_HE.md).*
