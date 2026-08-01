# AthleAgent — High-Level Design (HLD)

## Full-Project High-Level Design Document


| Field                 | Value                                                                                |
| --------------------- | ------------------------------------------------------------------------------------ |
| **Version**           | 1.2                                                                                  |
| **Date**              | 2026-07-22                                                                           |
| **Authors**           | Yahav Simon, Tzuf Feldon                                                             |
| **Audience**          | Developers, course evaluators, technical stakeholders                                |
| **Related documents** | [LLD.md](LLD.md) · [DOCKER.md](DOCKER.md) · [MODEL_SELECTION.md](MODEL_SELECTION.md) |


---

## 1. Executive Summary

**AthleAgent** is a sports-injury prevention platform. The system collects daily data from multiple sources — self-reported check-ins, a smartwatch (via Health Connect), and optional AI-powered meal analysis — and computes a **Daily Injury Risk Score**.

The system serves two user roles:

- **Athlete** — submits data, views personal risk, and receives recommendations.
- **Coach** — manages a team, approves join requests, and monitors aggregate roster risk.

---

## 2. Goals and Non-Functional Requirements

### 2.1 Business Goals


| Goal                        | Success Metric                                          |
| --------------------------- | ------------------------------------------------------- |
| Early injury-risk detection | Daily score 0–100 + Low/Medium/High band                |
| Reduced manual data entry   | Automatic watch sync + optional AI meal analysis        |
| Coach visibility            | Real-time team dashboard                                |
| Continuous improvement      | `run_pipeline.py` — retrain on synthetic data + promote |


### 2.2 Non-Functional Requirements

#### Reliability & Availability


| Requirement                     | Implementation                                                                                                                                                                                                                                                            |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Automatic retry**             | On HTTP **503**, the Android client (`ApiClient.kt`) retries the request up to **3** times with a **2 s** delay between attempts                                                                                                                                          |
| **Robustness to missing input** | The ML inference path auto-fills missing features (e.g. nutrition) from population defaults in the feature contract (`backend/data/model_feature_contract.json` / `nutrition_defaults.py`); imputed fields lower `prediction_confidence` instead of crashing the pipeline |
| **Availability**                | Cloud Firestore (managed) + stateless FastAPI; readiness via `GET /health` (200 healthy / 503 unhealthy)                                                                                                                                                                  |
|                                 |                                                                                                                                                                                                                                                                           |


#### Security & Access Control


| Requirement               | Implementation                                                                                                                                  |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| **Authentication**        | Access to app data and Cloud Firestore is gated on Firebase Authentication (Google + email/password)                                            |
| **Authorization**         | At the application layer: a **coach** may access only athletes registered on their team; an **athlete** may access only their own personal data |
| **Prediction API caveat** | `POST /predict/daily` currently has **no** token auth (`userId` in body) — see §8                                                               |


#### Maintainability & Low Coupling


| Requirement                  | Implementation                                                                                                                                                                                                                                 |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Layer separation**         | Low coupling across three independent layers: **Android app**, **FastAPI inference server**, and **offline ML pipeline** (`ML_model/`)                                                                                                         |
| **Transparent model update** | Retrain and promote a new artifact (`promoted.json` → `injury_model.pkl`) without changing Android app code, as long as the feature contract is preserved; backend loads the promoted artifact at startup (restart to pick up a new promotion) |
| **Privacy**                  | Health Connect permissions; `PrivacyPolicyActivity`                                                                                                                                                        


---

## 3. System Context

```mermaid
C4Context
    title AthleAgent — System Context

    Person(athlete, "Athlete", "Submits data and views risk")
    Person(coach, "Coach", "Manages team and monitors risk")

    System(athleagent, "AthleAgent", "Android app + ML backend")

    System_Ext(firebase, "Firebase", "Auth + Firestore")
    System_Ext(healthconnect, "Health Connect", "Watch / sensor data")
    System_Ext(gemini, "Google Gemini", "Vision + Text AI")
    System_Ext(wearables, "Wearables", "Garmin, Samsung, Pixel Watch...")

    Rel(athlete, athleagent, "Uses")
    Rel(coach, athleagent, "Uses")
    Rel(athleagent, firebase, "Auth, CRUD")
    Rel(athleagent, healthconnect, "Read health records")
    Rel(healthconnect, wearables, "Sync")
    Rel(athleagent, gemini, "Meal analysis, recommendations")
```



---

## 4. Logical Architecture — Three Layers

```mermaid
flowchart TB
    subgraph Client["Client Layer — Android (Kotlin)"]
        UI[Activities + View Binding]
        Auth[Firebase Auth UI]
        HC[Health Connect SDK]
        GemClient[Gemini SDK]
        FS_SDK[Firestore SDK]
        Retro[Retrofit → Backend]
    end

    subgraph Server["Service Layer — FastAPI (Python)"]
        API["/predict/daily"]
        PredSvc[Prediction Service]
        HistSvc[History Service]
        ML[XGBoost Model]
    end

    subgraph Data["Data Layer"]
        Firestore[(Cloud Firestore)]
    end

    subgraph MLOps["ML Pipeline (offline)"]
        Gen[generation/simulator]
        Train[training/pipeline]
        Promote[run_pipeline.py]
        Artifacts[(artifacts/injury_model.pkl)]
    end

    UI --> Auth
    UI --> HC
    UI --> GemClient
    UI --> FS_SDK
    UI --> Retro
    FS_SDK <--> Firestore
    Retro --> API
    API --> PredSvc
    PredSvc --> HistSvc
    HistSvc <--> Firestore
    PredSvc --> ML
    PredSvc --> HistSvc
    Gen --> Train --> Promote --> Artifacts
    Artifacts --> ML
```



### 4.1 Core Principle: Firestore as Source of Truth

- The Android app **writes** daily data to Cloud Firestore.
- The backend **reads** from Firestore, runs ML inference, and **writes back** prediction results.
- The app **reads** results from Firestore — not primarily from the HTTP response body.
- There is **no local SQL database**; all persistent application data lives in Cloud Firestore.

### 4.2 Separation of Responsibilities


| Component     | Responsibility                                              | Not Responsible For |
| ------------- | ----------------------------------------------------------- | ------------------- |
| **Android**   | UX, data collection, client-side Gemini, prediction trigger | ML inference        |
| **Backend**   | Firestore read/write, feature engineering, ML inference     | UI, meal vision     |
| **ML_model**  | Training, validation, promotion                             | Runtime serving     |
| **Firestore** | Persistent storage                                          | Computation         |


---

## 5. Roles and User Flows

### 5.1 Athlete — Daily Flow

```mermaid
sequenceDiagram
    participant A as Athlete App
    participant HC as Health Connect
    participant FS as Firestore
    participant BE as Backend API
    participant G as Gemini

    A->>HC: Morning sync (sleep + physical)
    HC-->>A: sleepMinutes, steps, HR, HRV...
    A->>FS: daily_health/{today} (+ yesterday load to {D-1} per policy)

    A->>A: Check-in (energy, soreness, stress)
    A->>FS: daily_checkins/{today}

    opt Meal
        A->>G: Meal photo
        G-->>A: calories, protein, carbs
        A->>FS: daily_nutrition/{today}
    end

    Note over A,BE: cross-trigger: either screen may call /predict/daily when gate passes (sleep>0 + yesterday steps>0 + survey)
    A->>BE: POST /predict/daily {userId, date}
    BE->>FS: read snapshot + history
    BE->>BE: XGBoost predict_proba
    BE->>FS: merge finalRiskScore, riskLevel, predictionConfidence
    BE-->>A: {risk_score, risk_level, prediction_confidence} (UI reads from Firestore)

    A->>FS: read daily_health/{today}
    A->>G: Text recommendations by risk
    A->>A: AthleteDashboard
```



**Cross-trigger conditions:**

Both `DailyCheckInActivity` and `WearableSyncActivity` run the same client gate after their write (`checkAndTriggerPredictionInBackground`). Either path may run first; `POST /predict/daily` fires only when **all** of the following hold:

| Condition | Source |
| --------- | ------ |
| `sleepMinutes > 0` | `daily_health/{today}` |
| `steps > 0` | `daily_health/{yesterday}` (prior-day load) |
| Check-in present with `energyLevel` | `daily_checkins/{today}` exists and contains `energyLevel` |

If any value is missing or zero, the app skips the API call (Logcat: `ML_Trigger` / “Skipping trigger”).

`MealAnalysisActivity` saves nutrition only — it does **not** call `POST /predict/daily`.

> **Gemini note:** Gemini runs client-side only and is optional for meal analysis. Daily injury-risk scoring works without Gemini.

### 5.2 Athlete — Daily Risk Activity Diagram (UC-01 + UC-05)

**Diagram type:** UML Activity Diagram (flowchart) · **Direction:** top → bottom · **UC:** 01 + 05

Cross-trigger: either path may run first; prediction fires only when the shared Android gate passes (`sleepMinutes > 0` on D, `steps > 0` on D-1, and today’s check-in with `energyLevel`).

```mermaid
%%{init: {"flowchart": {"htmlLabels": true, "curve": "linear", "nodeSpacing": 40, "rankSpacing": 45}, "theme": "base"}}%%
flowchart TB
    %% ===== UML Activity Diagram — Daily Injury Risk =====
    Start((▶ START<br/>Morning day D)) --> Fork{Which action<br/>first?}

    %% --- Path UC-05 ---
    Fork -->|left: UC-05 Wearable sync| Sync[① Read Health Connect]
    Sync --> WriteH[② Write daily_health<br/>sleep → D · load → D-1]
    WriteH --> Q1{③ Gate ready?<br/>sleep>0 · D-1 steps>0 · energyLevel}
    Q1 -->|YES →| Predict
    Q1 -->|NO →| Prompt1[/Prompt: complete morning survey<br/>or wait for non-zero HC data/]
    Prompt1 --> Survey

    %% --- Path UC-01 ---
    Fork -->|right: UC-01 Morning survey| Survey[① Fill survey<br/>energy · soreness · stress · injuredYesterday]
    Survey --> WriteC[② Write daily_checkins/D]
    WriteC --> Q2{③ Gate ready?<br/>sleep>0 · D-1 steps>0 · energyLevel}
    Q2 -->|YES →| Predict
    Q2 -->|NO →| Prompt2[/Prompt: sync wearable<br/>need sleep>0 and D-1 steps>0/]
    Prompt2 --> Sync

    %% --- Shared prediction pipeline ---
    Predict[[④ POST /predict/daily]]
    Predict --> BE[⑤ Backend: load snapshot + history<br/>XGBoost → score + confidence]
    BE --> Save[⑥ Merge into daily_health/D<br/>finalRiskScore · riskLevel · confidence]
    Save --> Dash[⑦ Show AthleteDashboard]
    Dash --> Q3{⑧ Gemini recommendation?}
    Q3 -->|YES optional →| Gem[Generate tip by risk level]
    Q3 -->|NO skip →| EndNode
    Gem --> EndNode((⏹ END))

    %% --- Legend styles ---
    classDef startEnd fill:#1B5E20,stroke:#0D3B12,color:#fff,stroke-width:2px
    classDef process fill:#E3F2FD,stroke:#1565C0,color:#0D47A1,stroke-width:1.5px
    classDef decision fill:#FFF8E1,stroke:#F9A825,color:#E65100,stroke-width:2px
    classDef system fill:#F3E5F5,stroke:#7B1FA2,color:#4A148C,stroke-width:1.5px
    classDef prompt fill:#FFF3E0,stroke:#EF6C00,color:#E65100,stroke-width:1.5px,stroke-dasharray: 5 3

    class Start,EndNode startEnd
    class Sync,WriteH,Survey,WriteC,Dash process
    class Fork,Q1,Q2,Q3 decision
    class Predict,BE,Save,Gem system
    class Prompt1,Prompt2 prompt
```



### 5.3 Coach — Team Join Activity Diagram (UC-04 + UC-07)

**Diagram type:** UML Activity Diagram with swimlanes · **Direction:** top → bottom · **UC:** 04 + 07

```mermaid
%%{init: {"flowchart": {"htmlLabels": true, "curve": "linear", "nodeSpacing": 35, "rankSpacing": 40}, "theme": "base"}}%%
flowchart TB
    %% ===== UML Activity Diagram — Join Team =====
    Start((▶ START)) --> Enter[Athlete enters teamCode]

    subgraph Athlete["🏊 Swimlane: Athlete  ·  UC-04"]
        direction TB
        Enter --> Query[Query Firestore:<br/>teams where teamCode == code]
        Query --> Found{Team found?}
        Found -->|NO →| Err[/Error: team not found/]
        Err --> Enter
        Found -->|YES →| Send[Create requests/{uid}<br/>status = pending]
        Send --> Wait((⏸ Wait for coach))
    end

    Wait --> Open

    subgraph Coach["🏊 Swimlane: Coach  ·  UC-07"]
        direction TB
        Open[Open CoachRequests] --> Load[Load pending requests]
        Load --> Any{Any pending?}
        Any -->|NO →| Empty[/Empty state/]
        Empty --> EndIdle((⏹ END — nothing to do))
        Any -->|YES →| Decide{Approve or reject?}
        Decide -->|REJECT →| Rej[Set status = rejected]
        Rej --> EndRej((⏹ END — rejected))
        Decide -->|APPROVE →| Batch
    end

    subgraph Firestore["🗄️ Swimlane: Firestore batch"]
        direction TB
        Batch[[Atomic batch]]
        Batch --> A1[status = approved]
        Batch --> A2[athletes arrayUnion uid]
        Batch --> A3[users.teamId = teamId]
        A1 --> Linked
        A2 --> Linked
        A3 --> Linked[Athlete linked to team]
    end

    Linked --> Dash[CoachDashboard reads<br/>daily_health per athlete]
    Dash --> EndOk((⏹ END — on roster))

    classDef startEnd fill:#1B5E20,stroke:#0D3B12,color:#fff,stroke-width:2px
    classDef wait fill:#455A64,stroke:#263238,color:#fff,stroke-width:2px
    classDef process fill:#E3F2FD,stroke:#1565C0,color:#0D47A1,stroke-width:1.5px
    classDef decision fill:#FFF8E1,stroke:#F9A825,color:#E65100,stroke-width:2px
    classDef system fill:#F3E5F5,stroke:#7B1FA2,color:#4A148C,stroke-width:1.5px
    classDef error fill:#FFEBEE,stroke:#C62828,color:#B71C1C,stroke-width:1.5px,stroke-dasharray: 5 3

    class Start,EndIdle,EndRej,EndOk startEnd
    class Wait wait
    class Enter,Query,Send,Open,Load,Dash,A1,A2,A3,Linked,Rej process
    class Found,Any,Decide decision
    class Batch system
    class Err,Empty error
```



### 5.4 Coach — Screen Flow

```mermaid
flowchart LR
    C[Coach Login] --> HT[HomeCoachActivity]
    HT --> CT[CreateTeamActivity]
    HT --> CR[CoachRequestsActivity]
    HT --> CD[CoachDashboardActivity]
    CR -->|approve| FS[(teams.athletes[])]
    CD -->|read| FS2[daily_health per athlete]
```



---

## 6. Data Model (High Level)

```mermaid
erDiagram
    USERS ||--o{ DAILY_HEALTH : has
    USERS ||--o{ DAILY_CHECKINS : has
    USERS ||--o{ DAILY_NUTRITION : has
    DAILY_NUTRITION ||--o{ MEALS : contains
    TEAMS ||--o{ REQUESTS : receives
    USERS ||--o| TEAMS : belongs_to

    USERS {
        string uid PK
        string role "athlete|coach"
        string teamId
        string birth_date "yyyy-MM-dd"
        int historyInjuryCount
    }

    DAILY_HEALTH {
        string date PK
        int sleepMinutes
        int steps
        int distanceMeters
        float hrvRmssd
        float finalRiskScore
        string riskLevel
        float predictionConfidence
        string aiRecommendation
    }

    DAILY_CHECKINS {
        string date PK
        int energyLevel
        int muscleSoreness
        int stressLevel
        int injuredYesterday
    }

    DAILY_NUTRITION {
        string date PK
        float totalCalories
        float totalProtein
        float totalCarbs
        int mealsLoggedCount
        bool imputed
    }

    MEALS {
        string mealId PK
        int calories
        int protein
        int carbs
    }

    TEAMS {
        string teamId PK
        string teamCode
        string TeamName
        string coachId
        array athletes
    }
```



> Field-level contract: `backend/data/model_feature_contract.json` · full `daily_health` / `daily_nutrition` fields: [LLD.md §2.7](LLD.md#27-firestore--app-writes)

---

## 7. External Integrations


| Service             | Direction                       | Usage                                                             | Code Location                                             |
| ------------------- | ------------------------------- | ----------------------------------------------------------------- | --------------------------------------------------------- |
| **Firebase Auth**   | Client → Google                 | Login, register, role routing                                     | `LoginActivity.kt`                                        |
| **Cloud Firestore** | Client ↔ Cloud, Backend ↔ Cloud | All application data                                              | Activities, `history/inference_bundle.py` + `persist.py`  |
| **Health Connect**  | Device → Client                 | sleep, steps, HR, HRV, VO2                                        | `WearableSyncActivity.kt`                                 |
| **Gemini API**      | Client → Google                 | Meal vision, coaching text (optional)                             | `AnalyzingMealActivity.kt`, `AthleteDashboardActivity.kt` |
| **FastAPI Backend** | Client → Server                 | `POST /predict/daily`, `POST /api/v1/observability/client-events` | `ApiClient.kt`, `observability/`                          |
| **XGBoost**         | Server (in-process)             | Injury probability                                                | `prediction/service.py`                                   |


### 7.1 Local Execution (Backend + ML)


| Path       | Command                                       | When to Use                 |
| ---------- | --------------------------------------------- | --------------------------- |
| **Docker** | `docker compose up --build` (repository root) | Evaluators, quick setup     |
| **Python** | `uvicorn main:app` from `backend/`            | Development with `--reload` |


> Docker guide: [DOCKER.md](DOCKER.md) · Android emulator → `http://10.0.2.2:8000` (no code changes required)

### 7.2 Configuration and Evaluation Credentials

**No `.env` file is required to run the backend.** Sensible defaults are defined in `backend/config.py`; optional overrides are documented in `backend/.env.example`.

For course evaluation, place credentials locally (do **not** commit secrets to the public repository):

- `backend/firebase-key.json` — Firebase Admin SDK service account (backend → Firestore); provide separately to evaluators
- `GEMINI_API_KEY` in `android_app/AthleAgent/local.properties` — Gemini for meal-photo analysis and recommendations; evaluator creates their own free key (Google AI Studio)
- `android_app/AthleAgent/app/google-services.json` — Firebase client configuration (already in the repo)

> **Security:** Keep the Admin service-account key and Gemini API key out of public archives. Prefer a private hand-off for those credentials.

---

## 8. Security — Current State and Recommendations

### 8.1 Current State


| Layer               | Mechanism                                                                                                                                  |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| User authentication | Firebase Auth (Google + email/password)                                                                                                    |
| Data authorization  | App-layer scoping (coach → team athletes only; athlete → own docs); Firestore Security Rules assumed/recommended for production (see §8.3) |
| Prediction API      | **No authentication** — `userId` supplied in request body                                                                                  |
| Backend → Firestore | Firebase Admin SDK (service account)                                                                                                       |


### 8.2 Known Risks

- Calling `/predict/daily` with an arbitrary `userId` (IDOR).
- No rate limiting on the prediction API.

### 8.3 Production Recommendations

1. Firebase ID Token verification on the backend.
2. Firestore Rules: athletes read only their own data; coaches read athletes in their team.
3. HTTPS + API Gateway / Cloud Run with IAM.

---

## 9. ML — High-Level Overview


| Stage          | Tool                                                          | Output                        |
| -------------- | ------------------------------------------------------------- | ----------------------------- |
| Synthetic data | `ML_model/generation/simulator.py` (CLI: `data_generator.py`) | `athlete_injury_data.csv`     |
| Training       | `ML_model/training/pipeline.py` (CLI: `train_model.py`)       | `injury_model.pkl` + manifest |
| Quality gates  | `validate_metrics.py`, `model_loader.py`                      | Recall ≥ 0.80, ROC-AUC ≥ 0.68 |
| Promotion      | `run_pipeline.py`                                             | `artifacts/promoted.json`     |
| Serving        | `POST /predict/daily`                                         | Probability → risk bands      |


### 9.1 Promoted Production Model (July 2026)


| Property                | Value                                                              |
| ----------------------- | ------------------------------------------------------------------ |
| **Model**               | `XGBoostCalibratedTuned`                                           |
| **Operating threshold** | ~0.10                                                              |
| **Feature count**       | 35 (see `backend/data/model_feature_contract.json`)                |
| **Quality gates**       | Recall ≥ 0.80, ROC-AUC ≥ 0.68 (from `backend/data/ml_policy.json`) |
| **Promotion pointer**   | `ML_model/artifacts/promoted.json` → run `20260709_104916`         |


> ML detail: [MODEL_SELECTION.md](MODEL_SELECTION.md)

---

## 10. Repository Structure

```
final_project_AthleAgent/
├── android_app/AthleAgent/     # Android application
├── backend/                    # FastAPI inference service
├── ML_model/                   # Training pipeline + artifacts
├── docs/                       # Project documentation (HLD/LLD/Docker)
├── logs/                       # athleagent.log (gitignored, backend + Android telemetry)
└── README.md
```

---

## 11. Dependencies and Technologies


| Layer    | Stack                                                                                                                                                                |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Mobile   | Kotlin, Android SDK, View Binding, Material, Retrofit, Gson, MPAndroidChart                                                                                          |
| Backend  | Python 3.x, FastAPI, Uvicorn, Pydantic, pandas, scikit-learn, XGBoost, firebase-admin                                                                                |
| Cloud    | Firebase Auth, Cloud Firestore                                                                                                                                       |
| AI       | Google Gemini (client-side only)                                                                                                                                     |
| Health   | Google Health Connect SDK                                                                                                                                            |
| CI/Tests | pytest — backend (253) + `ML_model` (12) via `[.github/workflows/backend-tests.yml](../.github/workflows/backend-tests.yml)`; Android JUnit placeholder (build only) |


---

## 12. Observability and Logging

Cross-cutting concern: correlate Android client actions with backend inference without a separate APM stack.


| Layer | Mechanism | Where |
| ----- | --------- | ----- |
| **Backend logs** | Structured `athleagent` logger → stdout + rotating file `logs/athleagent.log` | `backend/utils/logging.py` |
| **HTTP correlation** | `X-Request-ID` on every request; duration + status logged | `middleware/request_logging.py` |
| **Android → backend** | `POST /api/v1/observability/client-events` (errors, screen views, ML trigger, sync) | `ClientEventReporter.kt` → `observability.py` |
| **Client Logcat** | Local debug tags (e.g. `ML_Trigger` when prediction gate skips) | Activities / trigger helpers |

**Design notes:**

- Log records carry `request_id` and optional `user_id` for end-to-end tracing of a `/predict/daily` call.
- Client events are rate-limited server-side (`client_event_limiter.py`) and accepted with **202**.
- Persist failures after a successful inference are logged but do **not** fail the HTTP response (see LLD error table).
- Pytest runs configure logging to stdout only — they do not append to `logs/athleagent.log`.

> Field-level detail: [LLD.md § Observability](LLD.md#7-observability--logging) · [LLD.md § Testing](LLD.md#9-testing)

---

## 13. Testing and CI

Quality gates live next to the code they protect; CI runs on every relevant push.


| Suite | Framework | Scope (high level) | CI |
| ----- | --------- | ------------------ | --- |
| **Backend unit** | pytest (`unit` marker) | Feature engineering, preprocessing, prediction service, model loader gates, history/confidence, schemas | [`.github/workflows/backend-tests.yml`](../.github/workflows/backend-tests.yml) |
| **Backend integration** | pytest (`integration` marker) | `/predict/daily`, `/health`, `/status/ml`, OpenAPI contract, request-id / client-events, real-model smoke when artifact present | same workflow |
| **ML_model** | pytest | Policy ↔ `ml_policy.json`, train–serve parity (cold-start rolling defaults) | same workflow (second step) |
| **Android** | JUnit | Placeholder only — not in CI | — |

**Local commands:**

```bash
cd backend && python -m pytest tests/ -v
cd ML_model && python -m pytest tests/ -v
```

**ML quality gates (offline pipeline, not pytest):** Recall ≥ 0.80, ROC-AUC ≥ 0.68 — enforced by `validate_metrics.py` / `model_loader.py` before promotion.

> Full file map and markers: [LLD.md §9 Testing](LLD.md#9-testing) · run book: [README.md](../README.md#tests)

---

## 14. Known Limitations and Gaps


| Topic                    | Description                                                                                              |
| ------------------------ | -------------------------------------------------------------------------------------------------------- |
| **Android architecture** | Activity-centric + View Binding; no ViewModel/Repository layer (see README)                              |
| **Date-split sync**      | Implemented: sleep on `{D}`, load on `{D-1}`; **gap:** front-end gate does not verify `{D-1}` load > 0   |
| **Missing nutrition**    | Imputed from `nutrition_defaults.py` (2600 kcal, 130 g P, 300 g C); `nutritionImputed` lowers confidence |
| **Backend auth**         | Not implemented on production routes                                                                     |
| **Gemini on backend**    | API key may exist in config but no routes — Gemini runs client-side only                                 |
| **Prediction API auth**  | No authentication; `userId` in request body is a known limitation                                        |
| **UI data source**       | Dashboard reads `finalRiskScore` from Firestore, not primarily from the HTTP response                    |


---

## 15. Architectural Roadmap (Recommendations)

1. **API authentication** — Firebase token middleware.
2. **Android Repository layer** — separate Firestore access from Activities.
3. **Front-end trigger gate** — already enforced in app (`sleepMinutes > 0`, `{D-1}.steps > 0`, check-in `energyLevel`); keep in sync if feature inputs change.
4. **Cloud deployment** — backend on Cloud Run / Render (image buildable from existing `Dockerfile`).
5. **Firestore Rules** — hardening before production.

---

## 16. Document Map


| Document                                 | Content                                              |
| ---------------------------------------- | ---------------------------------------------------- |
| [DOCKER.md](DOCKER.md)                   | Backend + ML — Docker (evaluators)                   |
| [LLD.md](LLD.md)                         | Low-level design — APIs, pipelines, tests, logging   |
| [README.md](../README.md)                | Run locally / Docker, API, tests                     |
| [MODEL_SELECTION.md](MODEL_SELECTION.md) | Model selection protocol                             |


