# AthleAgent — סקירת קוד בקאנד (FastAPI)


| שדה               | ערך                                                                 |
| ----------------- | ------------------------------------------------------------------- |
| **גרסה**          | 1.1                                                                 |
| **תאריך**         | 2026-07-11                                                          |
| **קהל יעד**       | מפתחי Backend / ML, בוחני פרויקט גמר, reviewers                     |
| **היקף**          | `backend/` בלבד — ללא Android / אימון ML מלא                        |
| **מסמכים קשורים** | [HLD_PROJECT.md](HLD_PROJECT.md) · [backend/README.md](../backend/README.md) · [LOGGING_HE.md](LOGGING_HE.md) · [FRONTEND_CODE_REVIEW_HE.md](FRONTEND_CODE_REVIEW_HE.md) |


---

## 1. תקציר מנהלים

הבקאנד של AthleAgent הוא שירות **FastAPI** ל-inference של סיכון פציעה: הלקוח שולח `userId` + `date`, השרת טוען נתונים מ-Firestore, בונה וקטור פיצ'רים, מריץ מודל מקודם (promoted), וכותב תוצאה חזרה ל-`daily_health`.

**חוזקות:** שכבות ברורות (routes → service → history/preprocessing/ML), מדיניות merge מתועדת ליום התעוררות, שערי איכות מודל (Recall/AUC), חוזה פיצ'רים ב-JSON, correlation ID בלוגים, וסוללת unit/integration tests חזקה יחסית.

**חולשות עיקריות:** **אין אימות API** על `/predict/daily` למרות כתיבה עם service account, אין rate limit על inference, ספי המודל נטענים אך לא משמשים לסיווג, deps מיותרים ב-requirements.

| הערכה              | ציון | הערה                                                         |
| ------------------ | ---- | ------------------------------------------------------------ |
| פרויקט גמר / דמו   | 8/10 | זרימת inference שלמה, gates, טסטים, Docker localhost bind   |
| מוכנות לפרודקשן    | 4/10 | P0 באבטחה (אין auth)                                          |
| מבנה קוד וארגון    | 8/10 | שכבות טובות; `history/` מפוצל; Settings מ-env                |

---

## 2. היקף הסקירה

### 2.1 קבצים שנבדקו

| קטגוריה | נתיב |
| ------- | ---- |
| Entry / config | `main.py`, `config.py`, `.env.example` |
| Routes | `api/routes/health.py`, `predict.py`, `observability.py` |
| Prediction | `services/prediction/*.py` |
| History / Firestore | `services/history/*.py` |
| Preprocessing / features | `services/preprocessing/*`, `feature_engineering.py`, `model_features.py` |
| ML | `ml/model_loader.py`, `data/model_feature_contract.json` |
| Schemas / utils / middleware | `schemas/*`, `utils/*`, `middleware/request_logging.py` |
| בדיקות | `tests/unit/**`, `tests/integration/**`, `tests/conftest.py` |
| פריסה | `requirements.txt`, `../Dockerfile`, `../docker-compose.yml` |

**סה"כ:** ~48 מודולי production Python, ~28 קבצי test.

### 2.2 מה לא נכלל

- אפליקציית Android (`android_app/`) — ראו [FRONTEND_CODE_REVIEW_HE.md](FRONTEND_CODE_REVIEW_HE.md)
- אימון מודל מלא (`ML_model/train_model.py`, pipeline) — רק ממשק הטעינה וה-gates
- Firestore Security Rules (מחוץ לריפו / לא ב-`backend/`)

---

## 3. ארכיטקטורה

### 3.1 מבנה שכבות (כפי שמומש)

```
┌─────────────────────────────────────────────────────────────┐
│  FastAPI routes (predict / health / observability)          │
│    └── RequestLoggingMiddleware + CORS                      │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  services/prediction/service.py                             │
│    ├── firestore_mapping (wake-up merge policy)             │
│    ├── nutrition / profile defaults                         │
│    ├── preprocessing → feature_engineering                  │
│    ├── confidence + risk_levels                             │
│    └── ml/model_loader (gated estimator)                    │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
              Firestore (Admin SDK) + promoted joblib model
```

**יש:** הפרדת routes / services / schemas / ML, domain exceptions, feature contract, Settings מ-env (`pydantic-settings`), חבילת `history/` מפוצלת.

**אין:** Auth middleware, DI container, rate limit על prediction.

### 3.1.1 `services/history/` (אחרי פיצול)

| מודול | תפקיד | ~שורות |
| ----- | ----- | -----: |
| `firestore_io.py` | קריאות document / batch | ~35 |
| `inference_bundle.py` | טעינת snapshot+history לחיזוי | ~130 |
| `history_window.py` | חלון היסטוריה + confidence | ~170 |
| `persist.py` | שמירת תוצאת prediction | ~45 |
| `repository.py` | facade ל-re-export בלבד | ~40 |
### 3.2 זרימת `POST /predict/daily`

```
{userId, date}
  → predict_injury_daily
  → fetch_inference_firestore_bundle (batch + field projection)
  → injury_prediction_request_from_firestore_snapshot
       Sleep: daily_health/{D}
       Load:  daily_health/{D-1}
       Survey: daily_checkins/{D}
       Nutrition: daily_nutrition/{D-1}
  → predict_injury_risk (features → predict_proba → risk bands)
  → save_daily_prediction_result → daily_health/{date}
       finalRiskScore, riskLevel, predictionConfidence, predictionUpdatedAt
  → InjuryPredictionResponse
```

### 3.3 מה עובד טוב

| נושא | פירוט |
| ---- | ----- |
| Routes דקים | `predict.py` מתווך בלבד; הלוגיקה ב-service |
| Model gates | Recall≥0.80, AUC≥0.68 לפני `Live`; אחרת 503 |
| Feature contract | `model_feature_contract.json` + ולידציית עמודות |
| Observability | `X-Request-ID`, `user_id` ב-context, לוגים עם `event=` |
| Risk bands | מיושרים ל-Android (`int(p*100)` מול 20/70) |
| Docker demo | `127.0.0.1:8000` — mitigation מפורש לחוסר auth |
| טסטים | חלוקה unit/integration, fixtures ב-`conftest.py`, CI |

### 3.4 חולשות ארכיטקטוניות

| חומרה | ממצא | מיקום |
| ----- | ---- | ----- |
| P0 | אין auth — `userId` בגוף הבקשה הוא ה"הרשאה" היחידה | `api/routes/predict.py` |
| P1 | ספי מודל ב-bundle לא משמשים לסיווג | `bundle.py` ↔ `risk_levels.py` |
| P2 | `AuthorizationError` מוגדר אך לא בשימוש | `utils/exceptions.py` |
| P3 | deps לא בשימוש: `google-generativeai`, `pillow` | `requirements.txt` |

**תוקן ב-1.1:** Settings מ-env; פיצול `history/`; הסרת `fetch_daily_firestore_snapshot` + יישור docs.

---

## 4. ממצאים לפי חומרה

### 4.1 P0 — קריטי (חייב תיקון לפני פרודקשן / חשיפה ברשת)

| # | ממצא | קובץ | שורות | השפעה |
| - | ---- | ---- | ----- | ----- |
| 1 | **`POST /predict/daily` ללא אימות** — מתועד במפורש; כל מי שמגיע לפורט יכול להריץ inference | `api/routes/predict.py` | 41–56 | ניבוי / עומס על כל `userId` |
| 2 | **כתיבה מועדפת ל-Firestore** אחרי prediction — Admin SDK דורס `finalRiskScore` / `riskLevel` / `predictionConfidence` | `persist.py` (`save_daily_prediction_result`) | — | זיוף סיכון לספורטאי אחר |

~~P0 #3–5 (Settings / APP_ENV / OpenAPI / ungated fallback)~~ — **תוקן ב-1.1:** `config.py` הוא `pydantic-settings.BaseSettings`; Docker `APP_ENV=demo` נטען בפועל.

**הקלה קיימת:** `docker-compose.yml` קושר ל-`127.0.0.1:8000` בלבד. ההקלה **לא** חלה על `uvicorn --host 0.0.0.0` מקומי או פרסום פורט ציבורי.

### 4.2 P1 — גבוה

#### אבטחה ותפעול

| # | ממצא | קובץ | שורות |
| - | ---- | ---- | ----- |
| 1 | אין rate limit על `/predict/daily` (יש רק על client-events) | `predict.py` / `client_event_limiter.py` | — |
| 2 | `GET /status/ml` חושף gate/metrics ללא auth | `api/routes/predict.py` | 64–67 |
| 3 | `userId` נכתב ללוגים בכל prediction | `services/prediction/service.py` | 54–69 |
| 4 | נתוני Firestore נכתבים ע"י הלקוח; השרת סומך עליהם ("Trust frontend payloads") | `request_mapping.py` | 23–25 |

#### נכונות ML / train–serve

| # | ממצא | קובץ | שורות |
| - | ---- | ---- | ----- |
| 5 | `injury_threshold` / `medium_risk_threshold` נשלפים מה-bundle אך **לא בשימוש** — סיווג לפי `RISK_*_CUTOFF` בלבד | `bundle.py`, `service.py`, `risk_levels.py` | 52–79 / 93–96 / 19–34 |
| 6 | פרוקסי single-day ל-ACWR / sleep_ma7 / hrv_drop שונים מ-rolling האמיתי | `feature_engineering.py`, `rolling_features.py` | — |
| 7 | baselines קשיחים HRV=62, RHR=54 בחישוב `hrv_drop` | `feature_engineering.py` | 60–75 |
| 8 | clamp שינה 3–12 שעות רק בנתיב history, לא בנתיב request | `rolling_features.py` vs preprocessing | — |

#### מבנה ותחזוקה

| # | ממצא | קובץ | שורות |
| - | ---- | ---- | ----- |
| 9 | ~~`repository.py` God-module~~ — **תוקן ב-1.1** (פיצול ל-`firestore_io` / `inference_bundle` / `history_window` / `persist`) | `services/history/` | — |
| 10 | ~~תיעוד pydantic-settings ללא מימוש~~ — **תוקן ב-1.1** | `config.py` | — |
| 11 | deps מיותרים ב-image: `google-generativeai`, `pillow` (אין imports) | `requirements.txt` | 35–38 |

### 4.3 P2 — בינוני

| # | ממצא | קובץ | שורות |
| - | ---- | ---- | ----- |
| 1 | ~~`fetch_daily_firestore_snapshot` מת~~ — **הוסר ב-1.1**; docs עודכנו ל-`fetch_inference_firestore_bundle` | — | — |
| 2 | ~~Docs מצביעים על פונקציה ישנה~~ — **תוקן ב-1.1** | `backend/docs/*` | — |
| 3 | `AuthorizationError` + טסטים עליו — ללא שימוש ב-routes | `utils/exceptions.py` | 27–30 |
| 4 | `LOG_FORMAT=json` מתועד ב-`.env.example` אך הפורמטר טקסטואלי | `utils/logging.py` | — |
| 5 | ~~כפילות הרכבת שורות history~~ — **הופחת ב-1.1** (`history_rows_from_snapshots` משותף) | `history_window.py` | — |
| 6 | אם `history_context` חסר — `confidence` עלול לעשות round-trip נוסף ל-Firestore | `confidence.py` | ~50–58 |
| 7 | pytest ללא coverage gate | `pytest.ini` | — |
| 8 | אינטגרציית `/predict/daily` בעיקר mock של השירות — E2E Firestore מוגבל | `tests/integration/test_routes_predict_daily.py` | — |
| 9 | `*.pkl` לא ב-`.gitignore` (שורות מוערות) — סיכון commit של ארטיפקטים | `.gitignore` (שורש) | — |

### 4.4 P3 — נמוך

| # | ממצא | קובץ | שורות |
| - | ---- | ---- | ----- |
| 1 | `API_V1_PREFIX` קיים אך prediction בנתיב שורש (`/predict/daily`) | `config.py`, `predict.py` | — |
| 2 | FastAPI/uvicorn לא pinned כמו ה-ML stack | `requirements.txt` | 26–27 |
| 3 | חבילות test (`pytest`) בתוך requirements של runtime image | `requirements.txt` | 40–41 |
| 4 | הערות/docs ב-`backend/docs` בעברית — הקוד באנגלית (עקבי לפרויקט, לא באג) | `backend/docs/` | — |
| 5 | אין metrics/tracing מעבר ללוגים | — | — |

---

## 5. אבטחה — פירוט

### 5.1 חוסר אימות על prediction

```python
# api/routes/predict.py
@router.post("/predict/daily", response_model=InjuryPredictionResponse)
def predict_injury_daily(trigger: DailyPredictionTriggerRequest) -> InjuryPredictionResponse:
    """
    API auth is not enforced here — Android clients do not send Bearer tokens.
    Demo deployments should bind to localhost only (see docker-compose.yml).
    """
    ...
    persist_prediction_result_or_raise(trigger.userId, trigger.date, result)
```

**סיכון:** קורא ללא זהות יכול (א) להריץ מודל על כל משתמש, (ב) לכתוב תוצאות ל-Firestore עם הרשאות Admin.

**המלצה:** אימות Firebase ID token ב-middleware; וידוא ש-`uid` בטוקן == `userId` בגוף; rate limit לפי uid/IP.

### 5.2 סיכום משטח תקיפה

| נושא | מצב נוכחי |
| ---- | --------- |
| Auth | אין — רק הערה + bind localhost ב-compose |
| CORS | localhost:3000/8080 + credentials — סביר ל-demo |
| Secrets | `firebase-key.json` ב-gitignore; נטען מ-env path או קובץ מקומי |
| Rate limit | רק `/api/v1/observability/client-events` |
| OpenAPI | נסגר כש-`APP_ENV != "development"` (עובד עם Docker `APP_ENV=demo`) |
| Input validation | Pydantic על trigger; אין range clamp על מדדי בריאות מ-Firestore |

### 5.3 קשר לפרונטאנד

בסקירת Android צוין ש-`ApiClient` שולח רק `X-Request-ID` ללא Bearer. זה **עקבי** עם הבקאנד הנוכחי — שני הצדדים מתואמים על demo ללא auth, לא על פרודקשן.

---

## 6. קונפיגורציה ופריסה

### 6.1 טעינת Settings (תוקן ב-1.1)

`config.Settings` הוא `pydantic-settings.BaseSettings`: משתני סביבה, `backend/.env` ו-`.env` בשורש הפרויקט דורסים defaults.

| מקור | דוגמה | השפעה |
| ---- | ----- | ----- |
| Docker `APP_ENV=demo` | `openapi_enabled == False` | `/docs` כבוי |
| Docker `LOG_DIR=/app/logs` | לוגים לנתיב הקונטיינר | volume `./logs` |
| `.env` / compose | `RISK_*`, confidence weights, Firebase path | overrides בלי עריכת קוד |

מה שכן עובד דרך סביבה: כל שדות `Settings`, כולל `PORT` (גם ב-shell של הקונטיינר), `FIREBASE_SERVICE_ACCOUNT_KEY`, `APP_ENV`, `LOG_DIR`.

### 6.2 Docker

- Image: Python 3.12-slim, מעתיק `backend/` + artifacts מקודמים.
- Compose: bind `127.0.0.1:8000`, mount ל-firebase key, healthcheck על `/health`.
- `APP_ENV=demo` ב-compose סוגר OpenAPI וחוסם ungated fallback.

---

## 7. צינור prediction — פירוט

### 7.1 שלבים

1. טעינת bundle מ-Firestore (batch + projection)
2. מיפוי wake-up day → `InjuryPredictionRequest`
3. Imputation תזונה/גיל
4. Base features + derived proxies + same-day composites
5. העשרת history / defaults מ-contract
6. `predict_proba` → הסתברות
7. `classify_risk_level` לפי cutoffs UI
8. Persist ל-Firestore + תשובת API

### 7.2 Confidence

`0.6 * history + 0.4 * quality` → אחוז 0–100. חוסרים מורידים confidence אך **לא** חוסמים inference (מכוון).

### 7.3 פער train / serve

| נושא | אימון | Serve |
| ---- | ----- | ----- |
| סף חיובי | `threshold` במניפסט (~0.10 טיפוסי) | לא בשימוש לסיווג UI |
| רמות סיכון | — | 20% / 70% ל-Android |
| ACWR / sleep debt | rolling על היסטוריה | proxy ליום בודד כשאין היסטוריה |

הפער **מתועד חלקית** בקוד — אבל חובה להבהיר בבוחן/דוח שה-`risk_level` הוא שכבת תצוגה, לא החלטת הסף של האימון.

---

## 8. טיפול בשגיאות ו-observability

| מחלקה | HTTP | שימוש |
| ----- | ---- | ----- |
| `ValidationError` | 422 | יישור פיצ'רים / גיל לא תקין |
| `DatabaseError` | 503 | snapshot ריק / כשל persist |
| `MLModelError` | 503 | מודל לא Live |
| `AuthorizationError` | 403 | **לא בשימוש** |
| Exception כללי | 500 | `"Internal server error"` |

**חיובי:** handlers אחידים, קוד מכונה אופציונלי (`code=`), middleware עם משך בקשה וסינון health/docs.

**חסר:** JSON logging למרות התיעוד; אין מדדים (Prometheus וכו').

---

## 9. איכות קוד ותחזוקה

### 9.1 הקבצים הארוכים ביותר (production)

| שורות | מודול | הערה |
| ----: | ----- | ---- |
| ~254 | `ml/model_loader.py` | סביר יחסית למורכבות gates |
| ~176 | `services/preprocessing/request_features.py` | |
| ~170 | `services/history/history_window.py` | אחרי פיצול |
| ~132 | `schemas/inference.py` | |
| ~130 | `services/history/inference_bundle.py` | אחרי פיצול |
| ~115 | `services/prediction/service.py` | אורקסטרציה ברורה |

### 9.2 קוד מת / מיותר

| פריט | המלצה |
| ---- | ----- |
| ~~`fetch_daily_firestore_snapshot`~~ | **הוסר ב-1.1** |
| `AuthorizationError` (ללא שימוש) | השאר רק אם auth מתוכנן מיד; אחרת הסר |
| `google-generativeai`, `pillow` | הסר מ-`requirements.txt` |
| ספי bundle שלא בשימוש | או חבר לסיווג, או תעד במפורש "UI bands only" והסר מה-contract החובה |

### 9.3 שפה והערות

- קוד והערות מודולים: **אנגלית** — עקבי וטוב.
- `backend/docs/*.md`: עברית/אנגלית מעורבים — מתאים למסמכי פרויקט גמר.
- אין בעיית "הערות בעברית בתוך קוד production" כמו בפרונט.

---

## 10. בדיקות (Testing)

### 10.1 מה קיים

| סוג | דוגמאות |
| --- | ------- |
| Unit | preprocessing, features, confidence, risk bands, model_loader gates, history repository, schemas, limiter |
| Integration | `/predict/daily` shapes/errors, `/health`, `/status/ml`, OpenAPI contract, request logging |
| חוזה עמודות | `test_prediction_model_columns.py` (skip אם אין pkl) |

### 10.2 פערים

| פער | חומרה |
| --- | ----- |
| אין טסטי auth (middleware הוסר) | P1 (כשיוסיפו auth) |
| טענת env → Settings | **יש** (`tests/unit/test_config.py` — תוקן ב-1.1) |
| `/predict/daily` integration עם mock כבד | P2 |
| אין coverage threshold ב-CI | P2 |
| Docs מזכירים לפעמים קבצי טסט/auth ישנים | P2 |

**הערכה:** לבקאנד של פרויקט גמר — **כיסוי לוגיקת ML-serving טוב מאוד**; אבטחה עדיין החולשה העיקרית.

---

## 11. מפת Endpoints

| Method | Path | תפקיד | Auth |
| ------ | ---- | ------ | ---- |
| `POST` | `/predict/daily` | Inference + persist | אין |
| `GET` | `/status/ml` | סטטוס מודל / gates | אין |
| `POST` | `/test_predict` | Mock (כבוי כברירת מחדל) | אין + feature flag |
| `GET` | `/health` (ונתיבי health) | Liveness | אין |
| `POST` | `/api/v1/observability/client-events` | טלמטריית Android | אין + rate limit |

---

## 12. תוכנית תיקון מומלצת

### שלב 1 — לפני חשיפה מחוץ ל-localhost

| עדיפות | פעולה | ממצאים |
| ------ | ----- | ------ |
| 1 | Firebase ID token middleware + התאמת `uid` ל-`userId` | P0 #1–2 |
| 2 | Rate limit על `/predict/daily` | P1 #1 |
| 3 | להגן על `/status/ml` ב-auth (או לסגור מחוץ ל-dev) | P1 #2 |

### שלב 2 — Config אמיתי

| עדיפות | פעולה | ממצאים |
| ------ | ----- | ------ |
| 4 | ~~המרת Settings ל-pydantic-settings~~ | **בוצע ב-1.1** |
| 5 | ~~יישור docs~~ | **בוצע ב-1.1** (HLD/LLD/RISK_SCORE/BACKEND) |

### שלב 3 — בהירות ML

| עדיפות | פעולה | ממצאים |
| ------ | ----- | ------ |
| 7 | תיעוד מפורש: UI bands ≠ training threshold | P1 #5 |
| 8 | או שימוש ב-thresholds מה-bundle, או הסרת החובה עליהם ב-`resolve_model_bundle` | P1 #5 |
| 9 | יישור clamp שינה / תיעוד proxies | P1 #6–8 |

### שלב 4 — ניקוי

| עדיפות | פעולה | ממצאים |
| ------ | ----- | ------ |
| 10 | ~~מחיקת `fetch_daily_firestore_snapshot` / עדכון docs~~ | **בוצע ב-1.1** |
| 11 | הסרת deps מיותרים | P1 #11 |
| 12 | ~~פיצול `repository.py`~~ | **בוצע ב-1.1** |

### שלב 5 — בדיקות

| עדיפות | פעולה |
| ------ | ----- |
| 13 | טסטי auth (+ env→Settings כבר קיימים) |
| 14 | smoke E2E עם emulator/Firestore test doubles |
| 15 | coverage מינימלי ב-CI על `services/` + `ml/` |

---

## 13. נספח — רשימת קבצים לפי חומרה מקסימלית

| חומרה מקסימלית | קבצים |
| -------------- | ----- |
| **P0** | `api/routes/predict.py`, `services/history/persist.py`, `docker-compose.yml` (הקלה localhost בלבד) |
| **P1** | `services/prediction/bundle.py`, `services/risk_levels.py`, `services/feature_engineering.py`, `services/preprocessing/request_mapping.py`, `utils/client_event_limiter.py`, `requirements.txt` |
| **P2** | `utils/exceptions.py`, `utils/logging.py`, `services/prediction/confidence.py`, `.gitignore` |
| **P3** | `requirements.txt` (pins), חוסר metrics |

---

## 14. קוד מת ופריטים לניקוי

| חומרה | פריט | המלצה |
| ----- | ---- | ----- |
| ~~Medium~~ | ~~`fetch_daily_firestore_snapshot`~~ | **הוסר ב-1.1** |
| Medium | `google-generativeai`, `pillow` | הסר מ-requirements |
| Low | `AuthorizationError` ללא raise | מחק או חבר ל-auth עתידי |
| Low | שדות threshold ב-bundle אם נשארים UI-only | הפחת חובת ולידציה או השתמש בהם |

---

## 15. השוואה קצרה לפרונטאנד

| נושא | Android | Backend |
| ---- | ------- | ------- |
| Auth ל-API | אין Bearer | אין אימות — **אותה חולשה משותפת** |
| סודות | Gemini ב-BuildConfig (P0) | Service account בקובץ מקומי (gitignore) |
| ארכיטקטורה | God Activities | שכבות + `history/` מפוצל |
| טסטים | דלים ב-app | חזקים יחסית |
| מוכנות פרודקשן | 4/10 | 4/10 (auth עדיין חוסם) |

---

## 16. שינויי מסמך

| גרסה | תאריך | שינוי |
| ---- | ----- | ----- |
| 1.0 | 2026-07-11 | סקירה ראשונית מלאה של בקאנד FastAPI |
| 1.1 | 2026-07-11 | תיקון Settings מ-env; פיצול `history/`; הסרת snapshot ישן; עדכון ממצאים וdocs |
