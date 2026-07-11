# AthleAgent — סקירת קוד בקאנד (FastAPI)


| שדה               | ערך                                                                 |
| ----------------- | ------------------------------------------------------------------- |
| **גרסה**          | 1.0                                                                 |
| **תאריך**         | 2026-07-11                                                          |
| **קהל יעד**       | מפתחי Backend / ML, בוחני פרויקט גמר, reviewers                     |
| **היקף**          | `backend/` בלבד — ללא Android / אימון ML מלא                        |
| **מסמכים קשורים** | [HLD_PROJECT.md](HLD_PROJECT.md) · [backend/README.md](../backend/README.md) · [LOGGING_HE.md](LOGGING_HE.md) · [FRONTEND_CODE_REVIEW_HE.md](FRONTEND_CODE_REVIEW_HE.md) |


---

## 1. תקציר מנהלים

הבקאנד של AthleAgent הוא שירות **FastAPI** ל-inference של סיכון פציעה: הלקוח שולח `userId` + `date`, השרת טוען נתונים מ-Firestore, בונה וקטור פיצ'רים, מריץ מודל מקודם (promoted), וכותב תוצאה חזרה ל-`daily_health`.

**חוזקות:** שכבות ברורות (routes → service → history/preprocessing/ML), מדיניות merge מתועדת ליום התעוררות, שערי איכות מודל (Recall/AUC), חוזה פיצ'רים ב-JSON, correlation ID בלוגים, וסוללת unit/integration tests חזקה יחסית.

**חולשות עיקריות:** **אין אימות API** על `/predict/daily` למרות כתיבה עם service account, **`config.py` מתעלם ממשתני סביבה** (כולל `APP_ENV=demo` ב-Docker), אין rate limit על inference, ספי המודל נטענים אך לא משמשים לסיווג, וקיים drift בין תיעוד (pydantic-settings) לקוד (dataclass).

| הערכה              | ציון | הערה                                                         |
| ------------------ | ---- | ------------------------------------------------------------ |
| פרויקט גמר / דמו   | 8/10 | זרימת inference שלמה, gates, טסטים, Docker localhost bind   |
| מוכנות לפרודקשן    | 4/10 | P0 באבטחה + config שלא נטען מ-env                             |
| מבנה קוד וארגון    | 7/10 | שכבות טובות; `repository.py` God-module; קוד מת / deps מיותרים |

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

**יש:** הפרדת routes / services / schemas / ML, domain exceptions, feature contract.

**אין:** Auth middleware, DI container, rate limit על prediction, טעינת Settings מ-env.

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
| P0 | Settings לא נטענים מ-env / Docker | `config.py` |
| P1 | `repository.py` God-module (~402 שורות) | `services/history/repository.py` |
| P1 | ספי מודל ב-bundle לא משמשים לסיווג | `bundle.py` ↔ `risk_levels.py` |
| P2 | `fetch_daily_firestore_snapshot` מת / docs עדיין מצביעים עליו | `repository.py`, `docs/HLD.md` |
| P2 | `AuthorizationError` מוגדר אך לא בשימוש | `utils/exceptions.py` |
| P3 | deps לא בשימוש: `google-generativeai`, `pillow` | `requirements.txt` |

---

## 4. ממצאים לפי חומרה

### 4.1 P0 — קריטי (חייב תיקון לפני פרודקשן / חשיפה ברשת)

| # | ממצא | קובץ | שורות | השפעה |
| - | ---- | ---- | ----- | ----- |
| 1 | **`POST /predict/daily` ללא אימות** — מתועד במפורש; כל מי שמגיע לפורט יכול להריץ inference | `api/routes/predict.py` | 41–56 | ניבוי / עומס על כל `userId` |
| 2 | **כתיבה מועדפת ל-Firestore** אחרי prediction — Admin SDK דורס `finalRiskScore` / `riskLevel` / `predictionConfidence` | `repository.py` (`save_daily_prediction_result`) | 277–298 | זיוף סיכון לספורטאי אחר |
| 3 | **`Settings` הוא dataclass סטטי** — לא pydantic-settings; רוב משתני `.env` / Docker לא משפיעים | `config.py` | 26–114 | `APP_ENV=demo` ב-compose נשאר `"development"` בקוד |
| 4 | כתוצאה מ-#3: **OpenAPI נשאר פתוח** (`openapi_enabled` תלוי ב-`APP_ENV=="development"`) גם ב-Docker demo | `config.py`, `main.py` | 109–111 / 44–53 | חשיפת סכמה בסביבה "demo" |
| 5 | כתוצאה מ-#3: **fallback ללא manifest מותר** כי `APP_ENV` תמיד development כברירת מחדל | `ml/model_loader.py` | 205–228 | מודל לא-מקוּדם עלול להיטען כ-Live |

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
| 9 | `repository.py` ~402 שורות — I/O, history, persist, helpers | `services/history/repository.py` | — |
| 10 | תיעוד מצהיר pydantic-settings / override מ-env — הקוד לא מממש | `.env.example`, `README.md`, `docs/LLD.md` | — |
| 11 | deps מיותרים ב-image: `google-generativeai`, `pillow` (אין imports) | `requirements.txt` | 35–38 |

### 4.3 P2 — בינוני

| # | ממצא | קובץ | שורות |
| - | ---- | ---- | ----- |
| 1 | `fetch_daily_firestore_snapshot` לא בנתיב production (משתמשים ב-`fetch_inference_firestore_bundle`) | `repository.py` | 212–274 |
| 2 | Docs (`HLD`/`LLD`/`RISK_SCORE`) עדיין מתארים את הפונקציה הישנה | `backend/docs/*` | — |
| 3 | `AuthorizationError` + טסטים עליו — ללא שימוש ב-routes | `utils/exceptions.py` | 27–30 |
| 4 | `LOG_FORMAT=json` מתועד ב-`.env.example` אך הפורמטר טקסטואלי | `utils/logging.py` | — |
| 5 | כפילות הרכבת שורות history בין נתיבי bundle / `fetch_user_history` | `repository.py` | — |
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
| OpenAPI | אמור להיסגר מחוץ ל-development — **לא עובד** בגלל config |
| Input validation | Pydantic על trigger; אין range clamp על מדדי בריאות מ-Firestore |

### 5.3 קשר לפרונטאנד

בסקירת Android צוין ש-`ApiClient` שולח רק `X-Request-ID` ללא Bearer. זה **עקבי** עם הבקאנד הנוכחי — שני הצדדים מתואמים על demo ללא auth, לא על פרודקשן.

---

## 6. קונפיגורציה ופריסה

### 6.1 הפער בין docs לקוד

| מקור | מה נטען |
| ---- | ------- |
| `.env.example` / README | "pydantic-settings", overrides מ-env |
| `backend/docs/LLD.md` | דוגמת `class Settings(BaseSettings)` |
| **`config.py` בפועל** | `@dataclass` עם defaults בקוד; רק נתיב Firebase נקרא מ-`os.environ` |

משתנים ש-Docker מגדיר ו-**Settings מתעלם מהם:** `APP_ENV`, `LOG_DIR`, ורוב הכפתורים ב-`.env.example` (risk cutoffs, confidence weights, וכו').

מה שכן עובד דרך סביבה: `PORT` ב-shell של הקונטיינר, `FIREBASE_SERVICE_ACCOUNT_KEY` דרך `_default_firebase_key()`.

### 6.2 Docker

- Image: Python 3.12-slim, מעתיק `backend/` + artifacts מקודמים.
- Compose: bind `127.0.0.1:8000`, mount ל-firebase key, healthcheck על `/health`.
- המלצה לסקירה: לתקן טעינת Settings לפני שמסתמכים על `APP_ENV=demo`.

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
| 402 | `services/history/repository.py` | מועמד לפיצול |
| 254 | `ml/model_loader.py` | סביר יחסית למורכבות gates |
| 176 | `services/preprocessing/request_features.py` | |
| 132 | `schemas/inference.py` | |
| 115 | `services/prediction/service.py` | אורקסטרציה ברורה |

### 9.2 קוד מת / מיותר

| פריט | המלצה |
| ---- | ----- |
| `fetch_daily_firestore_snapshot` | מחק או סמן deprecated; עדכן docs |
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
| אין טסט שמוכיח טעינת env → Settings | P0/P1 — כרגע אין מה לבדוק |
| `/predict/daily` integration עם mock כבד | P2 |
| אין coverage threshold ב-CI | P2 |
| Docs מזכירים לפעמים קבצי טסט/auth ישנים | P2 |

**הערכה:** לבקאנד של פרויקט גמר — **כיסוי לוגיקת ML-serving טוב מאוד**; אבטחה וקונפיג חלשים כי החורים בקוד עצמו.

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
| 3 | לסגור `/docs` ו-`/status/ml` מחוץ ל-dev או להגן ב-auth | P0 #4, P1 #2 |

### שלב 2 — Config אמיתי

| עדיפות | פעולה | ממצאים |
| ------ | ----- | ------ |
| 4 | המרת `Settings` ל-pydantic-settings / קריאת env מפורשת | P0 #3–5 |
| 5 | יישור `.env.example`, README, LLD לקוד | P1 #10 |
| 6 | וידוא ש-`APP_ENV=demo` ב-Docker באמת משנה התנהגות | P0 #3 |

### שלב 3 — בהירות ML

| עדיפות | פעולה | ממצאים |
| ------ | ----- | ------ |
| 7 | תיעוד מפורש: UI bands ≠ training threshold | P1 #5 |
| 8 | או שימוש ב-thresholds מה-bundle, או הסרת החובה עליהם ב-`resolve_model_bundle` | P1 #5 |
| 9 | יישור clamp שינה / תיעוד proxies | P1 #6–8 |

### שלב 4 — ניקוי

| עדיפות | פעולה | ממצאים |
| ------ | ----- | ------ |
| 10 | מחיקת `fetch_daily_firestore_snapshot` / עדכון docs | P2 #1–2 |
| 11 | הסרת deps מיותרים | P1 #11 |
| 12 | פיצול `repository.py` (I/O / history / persist) | P1 #9 |

### שלב 5 — בדיקות

| עדיפות | פעולה |
| ------ | ----- |
| 13 | טסטי auth + העברת env ל-Settings |
| 14 | smoke E2E עם emulator/Firestore test doubles |
| 15 | coverage מינימלי ב-CI על `services/` + `ml/` |

---

## 13. נספח — רשימת קבצים לפי חומרה מקסימלית

| חומרה מקסימלית | קבצים |
| -------------- | ----- |
| **P0** | `api/routes/predict.py`, `services/history/repository.py` (persist), `config.py`, `ml/model_loader.py` (fallback+APP_ENV), `main.py` (OpenAPI), `docker-compose.yml` (הקלה בלבד) |
| **P1** | `services/prediction/bundle.py`, `services/risk_levels.py`, `services/feature_engineering.py`, `services/preprocessing/request_mapping.py`, `utils/client_event_limiter.py`, `requirements.txt`, `backend/.env.example` |
| **P2** | `services/history/repository.py` (legacy fetch), `utils/exceptions.py`, `utils/logging.py`, `services/prediction/confidence.py`, `backend/docs/*`, `.gitignore` |
| **P3** | `requirements.txt` (pins), חוסר metrics |

---

## 14. קוד מת ופריטים לניקוי

| חומרה | פריט | המלצה |
| ----- | ---- | ----- |
| Medium | `fetch_daily_firestore_snapshot` | מחק + עדכן HLD/LLD/RISK_SCORE |
| Medium | `google-generativeai`, `pillow` | הסר מ-requirements |
| Low | `AuthorizationError` ללא raise | מחק או חבר ל-auth עתידי |
| Low | שדות threshold ב-bundle אם נשארים UI-only | הפחת חובת ולידציה או השתמש בהם |
| Docs | אזכורי `BaseSettings` / auth middleware ישן | יישור למציאות |

---

## 15. השוואה קצרה לפרונטאנד

| נושא | Android | Backend |
| ---- | ------- | ------- |
| Auth ל-API | אין Bearer | אין אימות — **אותה חולשה משותפת** |
| סודות | Gemini ב-BuildConfig (P0) | Service account בקובץ מקומי (gitignore) |
| ארכיטקטורה | God Activities | שכבות טובות יותר |
| טסטים | דלים ב-app | חזקים יחסית |
| מוכנות פרודקשן | 4/10 | 4/10 (סיבות שונות) |

---

## 16. שינויי מסמך

| גרסה | תאריך | שינוי |
| ---- | ----- | ----- |
| 1.0 | 2026-07-11 | סקירה ראשונית מלאה של בקאנד FastAPI |
