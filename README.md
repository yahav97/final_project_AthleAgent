# 🏃‍♂️ AthleAgent

> **Shifting Athlete Care from Reaction to Prevention.**

[![Kotlin](https://img.shields.io/badge/Kotlin-Android-blue.svg)](https://kotlinlang.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![XGBoost](https://img.shields.io/badge/ML-XGBoost_%2B_scikit--learn-red.svg)](https://xgboost.readthedocs.io/)
[![Health Connect](https://img.shields.io/badge/Integration-Health_Connect-green.svg)](https://developer.android.com/health-and-fitness/guides/health-connect)
[![Gemini](https://img.shields.io/badge/AI-Gemini_Vision-orange.svg)](https://ai.google.dev/)

## 📖 Overview

Athlete injuries often follow from a mix of load, recovery, nutrition, and stress — usually tracked in separate tools. **AthleAgent** unifies those inputs into one daily **Injury Risk Score** (0–100%) for athletes and coaches.

The Android app collects data (check-ins, Health Connect, meal photos). A **FastAPI** backend reads from **Firestore**, runs **XGBoost** inference, and writes results back. The app displays scores and Gemini-generated recommendations.

## ✨ Core Features

* **📊 Daily Check-ins:** Short surveys for energy, muscle soreness, and stress.
* **🥗 AI Meal Analysis:** Gemini Vision extracts calories and macros from meal photos (client-side).
* **⌚ Health Connect Sync:** Sleep, steps, heart rate, HRV, and related metrics from wearables.
* **🤖 Predictive Risk Modeling:** Backend ML pipeline produces a daily injury-risk probability, risk level (Low/Medium/High), and confidence score.

## 🛠️ Tech Stack

| Layer | Technologies |
|-------|----------------|
| **Android** | Kotlin, Activities, View Binding, XML, Material, Retrofit, Gson |
| **Cloud** | Firebase Authentication, Cloud Firestore |
| **Backend** | Python, FastAPI, Uvicorn, Pydantic, firebase-admin |
| **ML (training & serving)** | XGBoost, scikit-learn, pandas, joblib — see `ML_model/` and `backend/` |
| **External APIs** | Google Health Connect, Google Gemini (Vision + text) |

### Android architecture (as implemented)

**Activity-centric** — not MVVM. There is no `ViewModel` or Repository layer in the codebase.

* Each screen is an `AppCompatActivity` with **View Binding**.
* Activities call **Firestore** and **Retrofit** directly for reads, writes, and `POST /predict/daily`.
* UI state and business logic live in the Activity classes under `android_app/AthleAgent/app/src/main/java/com/yahav/athleagent/ui/`.

### Backend & ML (as implemented)

* Inference runs on the **server** (`backend/ml/model_loader.py`, `POST /predict/daily`) — not on-device.
* Promoted model: **XGBoostDeep**, 36 features, quality gates before serving.
* Training pipeline: `ML_model/train_model.py`, `ML_model/run_pipeline.py`.

## 🏗️ System Architecture & Workflow

Two roles, routed after **Firebase Authentication**:

### Athlete app

* Register → request to join a coach's team.
* Log data: Health Connect sync, daily check-in, optional meal photo.
* Trigger prediction via backend → read `finalRiskScore` and `riskLevel` from Firestore.
* Dashboard: risk gauge, history chart (MPAndroidChart), Gemini recommendation text.

### Coach app

* Create a team, approve join requests.
* Team dashboard: athlete list, per-athlete risk score and trend chart.

```
Android (Activities) → Firestore (write daily data)
                    → FastAPI POST /predict/daily (trigger)
Backend             → Firestore (read snapshot, write prediction)
Android             → Firestore (read finalRiskScore for UI)
```

## 🧠 Design Philosophy

* **Usability:** Minimal manual entry; wearable sync and photo-based nutrition.
* **Reliability:** Missing-data defaults to defaults; model blocked if quality gates fail.
* **Supportability:** Separate repos/folders for Android, backend, and ML pipeline.
* **Performance:** Stateless backend inference; Firestore as source of truth for UI.

## 📱 Screenshots

| Architecture | Workflow | Screens | Athlete View | Coach View |
| :---: | :---: | :---: | :---: | :---: |
| <img src="https://github.com/yahav97/AthleAgent-App/blob/main/assets/archi.png?raw=true" width="200"/> | <img src="https://github.com/yahav97/AthleAgent-App/blob/main/assets/workflow.png?raw=true" width="200"/> | <img src="https://github.com/yahav97/AthleAgent-App/blob/main/assets/screens.png?raw=true" width="200"/> | <img src="https://github.com/yahav97/AthleAgent-App/blob/main/assets/Athlete.png?raw=true" width="200"/> | <img src="https://github.com/yahav97/AthleAgent-App/blob/main/assets/coach.png?raw=true" width="200"/> |

## 🚀 Getting Started

### Prerequisites

* Android Studio (recent version)
* Physical Android device (recommended) with [Health Connect](https://play.google.com/store/apps/details?id=com.google.android.apps.healthdata)
* Firebase project (`google-services.json`)
* Gemini API key (`local.properties`)
* Backend — **either** Docker (Option A) **or** Python 3.11+ venv (Option B):
  * **Docker:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed **and running** before `docker compose up` (see below)
  * **Python:** venv + `pip install` — see [`backend/README.md`](backend/README.md)
* `backend/firebase-key.json` — Firebase Admin service account (required for backend; not in git)

### Android app

1. Clone the repository:
   ```bash
   git clone https://github.com/yahav97/AthleAgent-App.git
   cd AthleAgent-App/android_app/AthleAgent
   ```
2. Open `android_app/AthleAgent` in Android Studio.
3. In `local.properties`:
   ```properties
   GEMINI_API_KEY=your_api_key_here
   ```
4. Place `google-services.json` in `android_app/AthleAgent/app/`.
5. Sync Gradle and run on a device.

### Backend (required for live predictions)

**Option A — Docker (recommended for reviewers)**

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Mac) if not already installed.
2. **Start Docker Desktop** and wait until it shows **Running** (whale icon in the system tray — not "Starting").
3. Verify the engine is up:
   ```powershell
   docker version
   ```
   You should see both **Client** and **Server** sections. If you get `dockerDesktopLinuxEngine: The system cannot find the file specified`, Docker is not running yet — open Docker Desktop and try again.
4. Place `backend/firebase-key.json` **before** the first run (see [`docs/DOCKER.md`](docs/DOCKER.md) if the file was missing on first attempt).
5. From the repository root:

```powershell
docker compose up --build
```

Full guide: [`docs/DOCKER.md`](docs/DOCKER.md)

Verify: `GET http://localhost:8000/status/ml` → `"status": "Live"`.

**Option B — Local Python**

From the repository root:

```bash
pip install -r backend/requirements.txt
cd backend
uvicorn main:app --reload
```

Verify: `GET http://localhost:8000/status/ml` → `"status": "Live"`.

Point the app Retrofit base URL at your backend host (see `ApiClient.kt` — emulator default `10.0.2.2:8000`).

## 📚 Documentation

| Document | Content |
|----------|---------|
| [`docs/HLD_PROJECT.md`](docs/HLD_PROJECT.md) | High-level design |
| [`docs/DOCKER.md`](docs/DOCKER.md) | Backend + ML via Docker |
| [`docs/NFR.md`](docs/NFR.md) | Non-functional requirements |
| [`backend/docs/RISK_SCORE.md`](backend/docs/RISK_SCORE.md) | Risk score pipeline end-to-end |
| [`backend/README.md`](backend/README.md) | Backend setup and API |

## 👨‍💻 Authors

* **Yahav Simon** — [GitHub](https://github.com/yahav97)
* **Tzuf Feldon**
