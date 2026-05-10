# הסבר על טסטי הבקאנד (`backend/tests/`)

מסמך זה מיועד למי שלא מכיר pytest או את המבנה של הפרויקט. אין כאן קוד חדש — רק תיאור במילים פשוטות.

## איך מריצים

מתיקיית `backend`:

```bash
python -m pytest tests/ -v
```

`-v` מציג את שם כל טסט. בלי זה רואים רק נקודות עבור/כישלון.

## מושגים קצרים

| מושג | משמעות |
|------|--------|
| **טסט יחידה (unit)** | בודק פונקציה או מודול בידוד — לרוב עם נתונים מזויפים (mocks). |
| **טסט אינטגרציה** | מפעיל את האפליקציה (FastAPI) או שרשרת אמיתית (למשל HTTP + שירות). |
| **monkeypatch** | בזמן הטסט מחליפים זמנית פונקציה אמיתית בגרסה מבוקרת — כדי לא לגעת ב-Firestore או במודל אמיתי. |
| **skipif** | מדלג על טסט אם תנאי לא מתקיים (למשל אין קובץ `injury_model.pkl`). |

---

## מפת קבצים (לפי נושא)

| קובץ | נושא עיקרי |
|------|------------|
| `test_inference.py` | חוזה HTTP של נקודות הקצה `/predict/daily`, `/predict/sklearn`, `/status/ml` |
| `test_inference_edge_cases.py` | קצה של קלט לחיזוי (שינה 0, מרחק גבוה וכו') — דרך השירות |
| `test_predict_error_mode.py` | וידוא שכשהמודל חסום מקבלים 500 תקין מ-`/predict/daily` |
| `test_feature_engineering.py` | פיצ'רים נגזרים (ACWR, עומס חד/כרוני) |
| `test_preprocessing.py` | המרה מבקשה ל-DataFrame, איכות נתונים (quality score) |
| `test_firestore_history.py` | חישוב היסטוריה של 7 ימים ורמת ביטחון (confidence) |
| `test_model_loader_gate.py` | שער איכות לפני טעינת מודל (manifest, Recall, AUC) |
| `test_prediction_model_columns.py` | התאמת עמודות למודל, נתיב מ-Firestore, persist |
| `test_train_serve_parity.py` | שהלוגיקה בדרך האימון ובדרך ה-serve לא סותרות את עצמן בברוטו |

---

## `test_inference.py` — חוזה HTTP

| טסט | מה הוא בודק |
|-----|----------------|
| `test_predict_daily_production_contract` | שליחת `POST /predict/daily` עם `userId` + `date`. אם יש Firestore/מודל — מצפים ל-200 ולשדות תשובה קבועים (`risk_score`, `risk_level`, וכו'). אם משהו נכשל בשרת — מצפים ל-500 עם `"Prediction unavailable"` (זה לגיטימי בסביבות בלי DB). |
| `test_predict_daily_minimal_trigger_contract` | מזייפים את `predict_injury_risk_from_firestore` ואת השמירה ל-Firestore — כדי לבדוק שמסלול ה-HTTP עובד ושה-persist נקרא, בלי תלות ברשת. |
| `test_predict_sklearn_legacy_endpoint_disabled_by_default` | הנתיב הישן `/predict/sklearn` חייב להחזיר **410** (לא בשימוש) כשה-flag כבוי. |
| `test_ml_status_endpoint_shape` | `GET /status/ml` מחזיר מפתחות קבועים (`status`, `gate_reason`, …) ו-`status` הוא `Live` או `Blocked`. |

---

## `test_inference_edge_cases.py` — קצה, בלי HTTP

הטסטים האלה קוראים ישירות ל-`predict_injury_risk(...)` עם `InjuryPredictionRequest` — לא דרך URL. המטרה: לוודא שלא קורסים על קלטים קיצוניים.

| טסט | מה הוא בודק |
|-----|----------------|
| `test_predict_extreme_sleep_zero_no_crash` | שינה 0 דקות — או חוזה תוצאה תקינה או זורק שגיאה צפויה; לא קריסה שקטה. |
| `test_predict_extreme_distance_high_no_crash` | מרחק/צעדים גבוהים מאוד — אותו עיקרון. |
| `test_predict_response_json_schema_when_success` | אם החיזוי הצליח, יש את השדות הבסיסיים בתשובה (כולל `data_quality_*`). |
| `test_status_endpoint_multiple_calls_light_load` | קורא ל-`/status/ml` 10 פעמים — בודק יציבות קלה. |
| `test_predict_missing_optional_fields_still_deterministic_error_or_success` | רק `userId` + `date` בשאר השדות — או שגיאה או הצלחה, אבל התנהגות דטרמיניסטית. |

---

## `test_predict_error_mode.py` — מודל לא זמין

| טסט | מה הוא בודק |
|-----|----------------|
| `test_predict_daily_returns_500_when_model_gate_blocks` | מזייף snapshot מ-Firestore, מכבה מודל (`get_model` מחזיר `None`), מדלג על persist. מצפים ל-**500** ולטקסט `"Prediction unavailable"` — כמו שקורה כשהמודל לא עומד בשער האיכות. |

---

## `test_feature_engineering.py` — הנדסת פיצ'רים

| טסט | מה הוא בודק |
|-----|----------------|
| `test_acwr_ratio_bounded` | `acwr_ratio` נשאר בטווח `[0.35, 2.8]`, ועומס חד/כרוני חיובי; הנוסחה תואמת את ה-clamp. |
| `test_rest_day_low_acute` | יום מנוחה (מרחק 0) — עומס חד לא שלילי; `sleep_debt_3d` יכול להיות 0 בתרחיש הזה. |

---

## `test_preprocessing.py` — לפני המודל

| טסט | מה הוא בודק |
|-----|----------------|
| `test_dataframe_shape_and_no_nan` | מהבקשה נוצר DataFrame בשורה אחת, עם כל העמודות המוגדרות ב-`MODEL_FEATURE_COLUMNS`, בלי NaN. |
| `test_stress_mapping_from_0_100_scale` | `stressLevel` מהסקאלה של האפליקציה ממופה לטווח שהמודל מצפה לו. |
| `test_types_float64` | כל העמודות מסוג מספרי צף — מתאים ל-sklearn. |
| `test_profile_fields_override_defaults_when_provided` | גיל והיסטוריית פציעות מהפרופיל נכנסים לשורת הפיצ'רים; `vo2_max` במודל נשאר קבוע מהשרת. |
| `test_quality_score_tolerates_missing_nutrition_fields` | בלי תזונה עדיין אפשר ציון איכות סביר ואין חסימה קשיחה. |
| `test_quality_score_sets_hard_blocker_without_load_signal` | בלי סיגנל עומס (צעדים/מרחק וכו') — יש חסימת איכות (`load_signal`). |

---

## `test_firestore_history.py` — חלון היסטוריה

| טסט | מה הוא בודק |
|-----|----------------|
| `test_compute_historical_derived_features_returns_rolling_values` | מ-7 ימים של דמה נגזרים כמו ACWR בטווח סביר. |
| `test_history_window_context_confidence_low_for_short_history` | רק יום אחד בהיסטוריה → `confidence` = `low`. |
| `test_history_window_context_can_exclude_target_day` | המערכת יודעת לא לכלול את יום היעד בשאילתת היסטוריה כשמבקשים. |
| `test_compute_historical_features_with_missing_days_uses_available_average` | חוסר ימים בשבוע — משתמשים בממוצע על מה שיש. |

---

## `test_model_loader_gate.py` — טעינת מודל בטוחה

| טסט | מה הוא בודק |
|-----|----------------|
| `test_load_model_rejects_corrupted_manifest` | קובץ manifest לא JSON תקין → המודל לא נטען, סיבה `manifest_corrupted`. |
| `test_load_model_rejects_manifest_below_recall_gate` | Recall מתחת לסף הקשיח → לא נטען, סיבה `manifest_recall_below_hard_gate`. |
| `test_load_model_rejects_manifest_below_auc_gate` | ROC-AUC נמוך מדי → לא נטען, סיבה `manifest_auc_too_low`. |

---

## `test_prediction_model_columns.py` — עמודות מול המודל ושירות החיזוי

| טסט | מה הוא בודק |
|-----|----------------|
| `test_predict_injury_risk_with_loaded_model_no_500` | **רק אם** קיים `injury_model.pkl`: קריאת HTTP ל-`/predict/daily` עם snapshot מזויף; אם 200 — `risk_score` בין 0 ל-1. אם 500 — הודעה צפויה. |
| `test_predict_injury_risk_service_subset_columns_skips_missing_estimator` | בלי מודל חי — השירות זורק `RuntimeError` עם טקסט קבוע. |
| `test_predict_injury_risk_raises_when_model_missing` | וידוא שנכשלים בצורה צפויה כשאין מודל. |
| `test_predict_quality_relaxed_when_history_backfills_missing_signals` | תרחיש מורכב עם הרבה monkeypatch — גם אחרי הרפיה של איכות, עדיין נכשלים על מודל חסום (הזרימה לא מסתירה את חוסר המודל). |
| `test_predict_injury_risk_from_firestore_maps_snapshot` | `predict_injury_risk_from_firestore` ממפה snapshot של Firestore לקריאה פנימית (כאן מזייפים את המשיכה ואת החיזוי). |
| `test_persist_prediction_result_or_raise_raises_when_write_fails` | אם שמירה ל-Firestore נכשלת — מתקבלת שגיאת persist. |
| `test_validate_feature_vector_enforces_exact_training_order` | וקטור הפיצ'רים מסודר בדיוק כמו שהמודל דורש. |
| `test_validate_feature_vector_raises_when_missing_column` | עמודה חסרה → `ValueError`. |

---

## `test_train_serve_parity.py` — אימון מול שירות

| טסט | מה הוא בודק |
|-----|----------------|
| `test_training_and_serving_derived_features_parity_within_tolerance` | משווה פיצ'רים שנגזרים בצד האימון (`ML_model/data_generator`) לבין `compute_derived_features` בשרות — עם טולרנס רחב (כי ב-serve זה קירוב). |
| `test_serving_proxy_direction_matches_training_signal_trends` | מצב "שחוק" לעומת "מאושש" — גם באימון וגם ב-serve הכיוון של חוב שינה ו-ACWR עקבי (מי גדול ממי). |

---

## סיכום שורה אחת

הטסטים מכסים: **צורת API**, **מה קורה כשאין מודל או אין נתונים**, **איכות קלט**, **היסטוריה של שבוע**, **שער טעינת מודל**, **התאמת עמודות ל-sklearn**, ו**עקביות גסה בין אימון לשרות**.

אם משהו לא ברור בטסט ספציפי — פתח את הקובץ ב-`backend/tests/` וחפש את שם הפונקציה שמתחילה ב-`test_`; השם אמור לשקף את כוונת הבדיקה.
