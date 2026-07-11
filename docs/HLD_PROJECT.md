# AthleAgent — High-Level Design (HLD)
## Full-Project High-Level Design Document

| Field | Value |
|-------|-------|
| **Version** | 1.1 |
| **Date** | 2026-07-11 |
| **Authors** | Yahav Simon, Tzuf Feldon |
| **Audience** | Developers, course evaluators, technical stakeholders |
| **Related documents** | [LLD_PROJECT.md](LLD_PROJECT.md) · [backend/docs/HLD.md](../backend/docs/HLD.md) · [DOCKER.md](DOCKER.md) |

---

## 1. Executive Summary

**AthleAgent** is a sports-injury prevention platform. The system collects daily data from multiple sources — self-reported check-ins, a smartwatch (via Health Connect), and optional AI-powered meal analysis — and computes a **Daily Injury Risk Score**.

The system serves two user roles:
- **Athlete** — submits data, views personal risk, and receives recommendations.
- **Coach** — manages a team, approves join requests, and monitors aggregate roster risk.

---

## 2. Goals and Non-Functional Requirements

### 2.1 Business Goals

| Goal | Success Metric |
|------|----------------|
| Early injury-risk detection | Daily score 0–100 + Low/Medium/High band |
| Reduced manual data entry | Automatic watch sync + optional AI meal analysis |
| Coach visibility | Real-time team dashboard |
| Continuous improvement | `run_pipeline.py` — retrain on synthetic data + promote |

### 2.2 Non-Functional Requirements

> **Full specification (metrics, targets, evidence):** [NFR.md](NFR.md)

| Requirement | Current Implementation |
|-------------|------------------------|
| **Availability** | Cloud Firestore (managed) + stateless FastAPI |
| **Performance** | Prediction < 2 s (Firestore read + XGBoost inference) |
| **Reliability** | Defaults for missing data; confidence score |
| **Security** | Firebase Auth on client; **no auth on prediction API** (see §8) |
| **Maintainability** | Modular layout: Android / Backend / ML_model |
| **Privacy** | Health Connect permissions; `PrivacyPolicyActivity` |

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

| Component | Responsibility | Not Responsible For |
|-----------|----------------|---------------------|
| **Android** | UX, data collection, client-side Gemini, prediction trigger | ML inference |
| **Backend** | Firestore read/write, feature engineering, ML inference | UI, meal vision |
| **ML_model** | Training, validation, promotion | Runtime serving |
| **Firestore** | Persistent storage | Computation |

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

    Note over A,BE: cross-trigger: check-in waits for sleepMinutes / sync waits for energyLevel
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

| Screen | Triggers prediction when |
|--------|--------------------------|
| `DailyCheckInActivity` | `sleepMinutes` exists in `daily_health/{today}` |
| `WearableSyncActivity` | `energyLevel` exists in `daily_checkins/{today}` |

`MealAnalysisActivity` saves nutrition only — it does **not** call `POST /predict/daily`.

> **Gemini note:** Gemini runs client-side only and is optional for meal analysis. Daily injury-risk scoring works without Gemini.

### 5.2 Coach — Flow

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
        float finalRiskScore
        string riskLevel
        float predictionConfidence
    }

    DAILY_CHECKINS {
        string date PK
        int energyLevel
        int muscleSoreness
        int stressLevel
        int injuredYesterday
    }

    TEAMS {
        string teamId PK
        string teamCode
        string TeamName
        string coachId
        array athletes
    }
```

> Field-level detail: [backend/docs/FEATURES.md](../backend/docs/FEATURES.md)

---

## 7. External Integrations

| Service | Direction | Usage | Code Location |
|---------|-----------|-------|---------------|
| **Firebase Auth** | Client → Google | Login, register, role routing | `LoginActivity.kt` |
| **Cloud Firestore** | Client ↔ Cloud, Backend ↔ Cloud | All application data | Activities, `history/repository.py` |
| **Health Connect** | Device → Client | sleep, steps, HR, HRV, VO2 | `WearableSyncActivity.kt` |
| **Gemini API** | Client → Google | Meal vision, coaching text (optional) | `AnalyzingMealActivity.kt`, `AthleteDashboardActivity.kt` |
| **FastAPI Backend** | Client → Server | `POST /predict/daily`, `POST /api/v1/observability/client-events` | `ApiClient.kt`, `observability/` |
| **XGBoost** | Server (in-process) | Injury probability | `prediction/service.py` |

### 7.1 Local Execution (Backend + ML)

| Path | Command | When to Use |
|------|---------|-------------|
| **Docker** | `docker compose up --build` (repository root) | Evaluators, quick setup |
| **Python** | `uvicorn main:app` from `backend/` | Development with `--reload` |

> Docker guide: [DOCKER.md](DOCKER.md) · Android emulator → `http://10.0.2.2:8000` (no code changes required)

### 7.2 Configuration and Evaluation Credentials

**No `.env` file is required to run the backend.** Sensible defaults are defined in `backend/config.py`; optional overrides are documented in `backend/.env.example`.

For course evaluation, the repository includes:
- `backend/firebase-key.json` — Firebase Admin SDK service account (backend → Firestore)
- `android_app/AthleAgent/app/google-services.json` — Firebase client configuration (Android app)

> **Security:** These credential files are included for evaluator convenience. The repository must remain **private** and must not be published publicly.

---

## 8. Security — Current State and Recommendations

### 8.1 Current State

| Layer | Mechanism |
|-------|-----------|
| User authentication | Firebase Auth (Google + email/password) |
| Data authorization | Firestore Security Rules (assumed in Firebase project) |
| Prediction API | **No authentication** — `userId` supplied in request body |
| Backend → Firestore | Firebase Admin SDK (service account) |

### 8.2 Known Risks

- Calling `/predict/daily` with an arbitrary `userId` (IDOR).
- No rate limiting on the prediction API.

### 8.3 Production Recommendations

1. Firebase ID Token verification on the backend.
2. Firestore Rules: athletes read only their own data; coaches read athletes in their team.
3. HTTPS + API Gateway / Cloud Run with IAM.

---

## 9. ML — High-Level Overview

| Stage | Tool | Output |
|-------|------|--------|
| Synthetic data | `ML_model/generation/simulator.py` (CLI: `data_generator.py`) | `athlete_injury_data.csv` |
| Training | `ML_model/training/pipeline.py` (CLI: `train_model.py`) | `injury_model.pkl` + manifest |
| Quality gates | `validate_metrics.py`, `model_loader.py` | Recall ≥ 0.80, ROC-AUC ≥ 0.68 |
| Promotion | `run_pipeline.py` | `artifacts/promoted.json` |
| Serving | `POST /predict/daily` | Probability → risk bands |

### 9.1 Promoted Production Model (July 2026)

| Property | Value |
|----------|-------|
| **Model** | `XGBoostCalibratedTuned` |
| **Operating threshold** | ~0.10 |
| **Feature count** | 35 (see `backend/data/model_feature_contract.json`) |
| **Quality gates** | Recall ≥ 0.80, ROC-AUC ≥ 0.68 |
| **Promotion pointer** | `ML_model/artifacts/promoted.json` → run `20260709_104916` |

> ML detail: [backend/docs/MODEL.md](../backend/docs/MODEL.md) · [RISK_SCORE.md](../backend/docs/RISK_SCORE.md)

---

## 10. Repository Structure

```
final_project_AthleAgent/
├── android_app/AthleAgent/     # Android application
├── backend/                    # FastAPI inference service
├── ML_model/                   # Training pipeline + artifacts
├── docs/                       # Project documentation (HLD/LLD/NFR)
├── logs/                       # athleagent.log (gitignored, backend + Android telemetry)
└── README.md
```

---

## 11. Dependencies and Technologies

| Layer | Stack |
|-------|-------|
| Mobile | Kotlin, Android SDK, View Binding, Material, Retrofit, Gson, MPAndroidChart |
| Backend | Python 3.x, FastAPI, Uvicorn, Pydantic, pandas, scikit-learn, XGBoost, firebase-admin |
| Cloud | Firebase Auth, Cloud Firestore |
| AI | Google Gemini (client-side only) |
| Health | Google Health Connect SDK |
| CI/Tests | pytest (backend), JUnit (Android placeholder) |

---

## 12. Known Limitations and Gaps

| Topic | Description |
|-------|-------------|
| **Android architecture** | Activity-centric + View Binding; no ViewModel/Repository layer (see README) |
| **Date-split sync** | Implemented: sleep on `{D}`, load on `{D-1}`; **gap:** front-end gate does not verify `{D-1}` load > 0 |
| **Missing nutrition** | Imputed from `nutrition_defaults.py` (2600 kcal, 130 g P, 300 g C); `nutritionImputed` lowers confidence |
| **Backend auth** | Not implemented on production routes |
| **Gemini on backend** | API key may exist in config but no routes — Gemini runs client-side only |
| **Prediction API auth** | No authentication; `userId` in request body is a known limitation |
| **UI data source** | Dashboard reads `finalRiskScore` from Firestore, not primarily from the HTTP response |

---

## 13. Architectural Roadmap (Recommendations)

1. **API authentication** — Firebase token middleware.
2. **Android Repository layer** — separate Firestore access from Activities.
3. **Front-end trigger gate** — verify `sleepMinutes > 0` and `{D-1}` load before `/predict/daily`.
4. **Cloud deployment** — backend on Cloud Run / Render (image buildable from existing `Dockerfile`).
5. **Firestore Rules** — hardening before production.

---

## 14. Document Map

| Document | Content |
|----------|---------|
| [DOCKER.md](DOCKER.md) | Backend + ML — Docker (evaluators) |
| [LLD_PROJECT.md](LLD_PROJECT.md) | Low-level design — full project |
| [backend/docs/HLD.md](../backend/docs/HLD.md) | Backend HLD |
| [backend/docs/LLD.md](../backend/docs/LLD.md) | Backend LLD |
| [backend/docs/BACKEND.md](../backend/docs/BACKEND.md) | Backend architecture |
| [backend/docs/FEATURES.md](../backend/docs/FEATURES.md) | Production data contract |
| [docs/NFR.md](NFR.md) | Non-functional requirements (metrics, gates, performance) |
| [docs/LOGGING_HE.md](LOGGING_HE.md) | Unified logging + Android telemetry |
| [backend/docs/MODEL.md](../backend/docs/MODEL.md) | Production ML config (gates, bands) |
| [backend/docs/RISK_SCORE.md](../backend/docs/RISK_SCORE.md) | End-to-end risk-score pipeline |
