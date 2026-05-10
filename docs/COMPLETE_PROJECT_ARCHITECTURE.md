# AthleAgent - Complete Project Architecture

## תוכן עניינים

1. [סקירה כללית](#סקירה-כללית)
2. [מבנה הפרויקט המלא](#מבנה-הפרויקט-המלא)
3. [ML Model - מודל למידת מכונה](#ml-model)
4. [Backend Architecture](#backend-architecture)
5. [Android App Architecture](#android-app-architecture)
6. [Data Flow & Integration](#data-flow--integration)
7. [API Contracts](#api-contracts)
8. [Database Schema](#database-schema)
9. [File Dependencies & Imports](#file-dependencies--imports)
10. [Use Cases Implementation](#use-cases-implementation)

---

## סקירה כללית

**AthleAgent** היא מערכת חכמה למעקב וחיזוי סיכון לפציעות בעזרת מודל למידת מכונה.

### מצב מערכת נוכחי (2026)

- **נתוני אפליקציה ותוצאות חיזוי:** נשמרים ב-**Firebase / Firestore** (מסמכי משתמש, `daily_health`, וכו'). אין שרת SQL (PostgreSQL) בבקאנד הנוכחי.
- **המלצת טקסט של המודל:** נוצרת ב-**בקאנד** (`recommendation` ב-API, `backendRecommendation` ב-Firestore); תבניות קבועות לפי הסתברות מודל + ACWR + משפט confidence. זה נפרד מהמלצת ניסוח אופציונלית מ-**Gemini** באפליקציה.
- **תיעוד מעודכן:** `backend/docs/README_HE.md`, `DATA_CONTRACT_FRONTEND_BACKEND.md`, `ATHLETE_DB_DATA_LIFECYCLE_HE.md`.

### ארכיטקטורה (סכימתי — מצב נוכחי)

```
┌─────────────────┐
│  Android App    │  (Kotlin)
│  (Frontend)     │
└────────┬────────┘
         │ HTTP/REST API
         │ Firebase Auth (אפליקציה)
         ▼
┌─────────────────┐
│  FastAPI        │  (Python)
│  Backend        │
└────────┬────────┘
         │
    ┌────┴────┬──────────────┬─────────────┐
    │         │              │             │
    ▼         ▼              ▼             ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│Firestore │ │Gemini AI │ │Health    │ │ML Model  │
│(App data)│ │(אופציונלי│ │Connect   │ │(scikit/  │
│          │ │ בלקוח)   │ │(Android) │ │joblib)   │
└──────────┘ └──────────┘ └──────────┘ └──────────┘
```

### טכנולוגיות

- **Frontend**: Android (Kotlin), Health Connect SDK
- **Backend**: FastAPI (Python), שירות חיזוי ML, אינטגרציה ל-Firestore לצורך קריאה/כתיבת תוצאות
- **ML**: scikit-learn, (לפי הארטיפקט המקודם) joblib
- **External APIs**: Google Gemini AI (למשל ניתוח תמונות באפליקציה), Firebase
- **Authentication**: Firebase Auth בצד האפליקציה (לא JWT מבקאנד SQL ביישום הנוכחי)

---

## מבנה הפרויקט המלא

```
final_project_AthleAgent/
├── android_app/
│   └── AthleAgent/
│       ├── app/
│       │   ├── src/
│       │   │   └── main/
│       │   │       ├── java/com/yahav/athleagent/
│       │   │       │   ├── MainActivity.kt
│       │   │       │   ├── logic/
│       │   │       │   │   ├── LoginManager.kt
│       │   │       │   │   ├── ApiClient.kt          # HTTP client for backend
│       │   │       │   │   ├── AuthManager.kt        # JWT token management
│       │   │       │   │   ├── HealthConnectManager.kt # Health Connect integration
│       │   │       │   │   └── DataSyncService.kt     # Background sync service
│       │   │       │   ├── ui/
│       │   │       │   │   ├── login/
│       │   │       │   │   │   ├── LoginActivity.kt
│       │   │       │   │   │   └── RegisterActivity.kt
│       │   │       │   │   ├── dashboard/
│       │   │       │   │   │   ├── DashboardActivity.kt
│       │   │       │   │   │   └── PredictionCard.kt
│       │   │       │   │   ├── nutrition/
│       │   │       │   │   │   ├── NutritionActivity.kt
│       │   │       │   │   │   └── CameraActivity.kt
│       │   │       │   │   ├── survey/
│       │   │       │   │   │   └── StressSurveyActivity.kt
│       │   │       │   │   ├── history/
│       │   │       │   │   │   └── HistoryActivity.kt
│       │   │       │   │   └── coach/
│       │   │       │   │       ├── CoachDashboardActivity.kt
│       │   │       │   │       ├── TeamManagementActivity.kt
│       │   │       │   │       └── AthleteListActivity.kt
│       │   │       │   ├── models/
│       │   │       │   │   ├── User.kt
│       │   │       │   │   ├── DailyRecord.kt
│       │   │       │   │   ├── Prediction.kt
│       │   │       │   │   ├── Team.kt
│       │   │       │   │   └── NutritionRecord.kt
│       │   │       │   └── utils/
│       │   │       │       ├── DateUtils.kt
│       │   │       │       └── ValidationUtils.kt
│       │   │       └── res/
│       │   │           ├── layout/          # XML layouts
│       │   │           ├── values/          # Strings, colors, dimensions
│       │   │           └── drawable/        # Images, icons
│       │   └── build.gradle.kts
│       └── build.gradle.kts
├── backend/
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py              # Configuration (DB, secrets, APIs)
│   ├── injury_model.pkl       # Trained ML model (loaded at startup)
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py      # PostgreSQL connection pool
│   │   └── migrations/        # Alembic migrations
│   ├── models/                # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── user.py           # User model (Athlete/Coach)
│   │   ├── team.py           # Team model
│   │   ├── team_member.py    # Team membership
│   │   ├── join_request.py   # Join team requests
│   │   ├── daily_record.py   # Daily metrics
│   │   ├── prediction.py     # Prediction history
│   │   ├── nutrition_record.py # Nutrition data
│   │   ├── stress_survey.py  # Daily stress surveys
│   │   └── health_connect.py # Health Connect permissions
│   ├── schemas/               # Pydantic schemas (DTOs)
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── team.py
│   │   ├── daily_record.py
│   │   ├── prediction.py
│   │   ├── nutrition.py
│   │   └── survey.py
│   ├── repositories/          # Data access layer
│   │   ├── __init__.py
│   │   ├── user_repository.py
│   │   ├── team_repository.py
│   │   ├── daily_record_repository.py
│   │   ├── prediction_repository.py
│   │   ├── nutrition_repository.py
│   │   └── survey_repository.py
│   ├── services/              # Business logic
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── prediction_service.py
│   │   ├── metrics_service.py
│   │   ├── team_service.py
│   │   ├── nutrition_service.py
│   │   └── health_connect_service.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── teams.py
│   │   │   ├── daily_data.py
│   │   │   ├── predictions.py
│   │   │   ├── nutrition.py
│   │   │   ├── surveys.py
│   │   │   └── health_connect.py
│   │   └── dependencies.py   # Auth dependencies
│   ├── ml/
│   │   ├── __init__.py
│   │   └── model_loader.py    # Load & use injury_model.pkl
│   ├── external/
│   │   ├── __init__.py
│   │   ├── gemini_service.py  # Google Gemini API
│   │   └── health_connect.py   # Health Connect API client
│   └── utils/
│       ├── __init__.py
│       ├── logging.py
│       └── exceptions.py
├── ML_model/
│   ├── train_model.py         # Model training script
│   ├── data_generator.py      # Synthetic data generation
│   ├── athlete_injury_data.csv # Training dataset
│   ├── athlete_injury_validation.csv # Validation dataset
│   ├── feature_importance.csv # Feature importance analysis
│   └── model_comparison.csv   # Model comparison results
├── docs/
│   ├── BACKEND_ARCHITECTURE.md
│   └── COMPLETE_PROJECT_ARCHITECTURE.md (this file)
├── requirements.txt           # Python dependencies
└── .gitignore
```

---

## ML Model

### Overview

המודל משתמש ב-**Random Forest**, **XGBoost**, **Logistic Regression**, או **SVM** לחיזוי סיכון לפציעה.

### Model Training Flow

```
data_generator.py
    ↓
Generates synthetic athlete data (7000 samples)
    ↓
train_model.py
    ↓
1. Load data (athlete_injury_data.csv)
2. Feature selection (remove weak features)
3. Train multiple models
4. Compare models (F1-Score, Recall, Precision)
5. Select best model (safety-focused)
6. Save model (injury_model.pkl)
7. Evaluate on validation set
```

### Features Used by Model

**Base Features** (19 features):
- `age`, `bmi`, `history_injury_count`, `vo2_max` *(exists in the trained artifact for compatibility; **not** collected in the product — inference uses a fixed constant)*
- `daily_distance_km`, `workout_intensity_minutes`, `avg_cadence`
- `sleep_hours`, `hrv_score`, `resting_hr`
- `daily_calories`, `total_calories_burned`, `calorie_balance`
- `acute_load_7d`, `chronic_load_21d`, `acwr_ratio`
- `sleep_debt_3d`, `hrv_drop`

**Weak Features Removed** (automatically detected):
- `stress_level` (importance < 0.03)
- `muscle_soreness` (importance < 0.03)

**Calculated Features** (from history):
- `acute_load_7d`: 7-day rolling average of daily_distance_km
- `chronic_load_21d`: 21-day rolling average of daily_distance_km
- `acwr_ratio`: acute_load_7d / chronic_load_21d
- `sleep_debt_3d`: Cumulative sleep deficit over 3 days
- `hrv_drop`: Current HRV - 7-day HRV average

### Model Selection Criteria

1. **Safety-Focused**: High Recall (catch injuries) > High Precision
2. **Threshold**: 0.25-0.4 (lower than default 0.5 for imbalanced data)
3. **Metrics**: F1-Score, Recall, Precision, ROC-AUC

### Model File

- **Location**: `backend/injury_model.pkl`
- **Format**: joblib pickle file
- **Contains**: Trained model + scaler (if needed) + feature names

### Model Loading (Backend)

```python
# backend/ml/model_loader.py
import joblib
import os

class ModelLoader:
    def __init__(self):
        model_path = os.path.join(os.path.dirname(__file__), '../injury_model.pkl')
        self.model = joblib.load(model_path)
        # Model expects specific features (after weak features removed)
    
    def predict(self, features_dict):
        # Prepare features matching model's expected format
        # Remove weak features if present
        # Scale if needed (for SVM/Logistic Regression)
        # Return: risk_percentage (0-100)
```

---

## Backend Architecture

### Project Structure

```
backend/
├── main.py                    # FastAPI app, route registration
├── config.py                  # Settings from environment variables
├── database/
│   ├── connection.py          # SQLAlchemy engine, session factory
│   └── migrations/            # Alembic migration files
├── models/                     # SQLAlchemy ORM (database tables)
├── schemas/                    # Pydantic (request/response validation)
├── repositories/               # Data access (CRUD operations)
├── services/                   # Business logic
├── api/routes/                 # HTTP endpoints
├── ml/                        # ML model integration
├── external/                   # External API clients
└── utils/                      # Utilities (logging, exceptions)
```

### File Dependencies (Backend)

#### main.py
```python
from fastapi import FastAPI
from api.routes import auth, teams, daily_data, predictions, nutrition, surveys, health_connect
from database.connection import engine, Base
from config import settings

app = FastAPI()
# Register all routes
app.include_router(auth.router, prefix="/auth")
app.include_router(teams.router, prefix="/teams")
# ...
```

#### api/routes/predictions.py
```python
from fastapi import APIRouter, Depends
from services.prediction_service import PredictionService
from services.metrics_service import MetricsService
from repositories.daily_record_repository import DailyRecordRepository
from repositories.prediction_repository import PredictionRepository
from api.dependencies import get_current_user
from ml.model_loader import ModelLoader

router = APIRouter()

@router.get("/predictions/today")
async def get_today_prediction(
    current_user = Depends(get_current_user),
    prediction_service: PredictionService = Depends()
):
    # Get user's daily data
    # Calculate metrics (ACWR, etc.)
    # Load ML model
    # Predict
    # Save prediction
    # Return risk percentage
```

#### services/prediction_service.py
```python
from ml.model_loader import ModelLoader
from services.metrics_service import MetricsService
from repositories.daily_record_repository import DailyRecordRepository

class PredictionService:
    def __init__(self):
        self.model_loader = ModelLoader()
        self.metrics_service = MetricsService()
        self.daily_repo = DailyRecordRepository()
    
    async def predict_injury_risk(self, user_id: UUID, date: date):
        # 1. Get daily record for date
        # 2. Get historical data (21 days for chronic_load)
        # 3. Calculate metrics (ACWR, sleep_debt, hrv_drop)
        # 4. Prepare features dict
        # 5. Remove weak features
        # 6. Call model.predict_proba()
        # 7. Return risk_percentage, risk_level, recommendations
```

#### services/metrics_service.py
```python
from repositories.daily_record_repository import DailyRecordRepository
import pandas as pd

class MetricsService:
    def __init__(self):
        self.daily_repo = DailyRecordRepository()
    
    def calculate_acwr(self, user_id: UUID, date: date):
        # Get last 21 days of daily_distance_km
        # Calculate acute_load_7d (last 7 days average)
        # Calculate chronic_load_21d (last 21 days average)
        # Return acwr_ratio
    
    def calculate_sleep_debt(self, user_id: UUID, date: date):
        # Get last 3 days of sleep_hours
        # Calculate: sum(8 - sleep_hours) for each day
        # Return sleep_debt_3d
    
    def calculate_hrv_drop(self, user_id: UUID, date: date):
        # Get current hrv_score
        # Get last 7 days average hrv_score
        # Return: current - average
```

#### repositories/daily_record_repository.py
```python
from sqlalchemy.orm import Session
from models.daily_record import DailyRecord
from database.connection import get_db

class DailyRecordRepository:
    def get_by_user_and_date(self, db: Session, user_id: UUID, date: date):
        return db.query(DailyRecord).filter(
            DailyRecord.user_id == user_id,
            DailyRecord.date == date
        ).first()
    
    def get_history(self, db: Session, user_id: UUID, days: int):
        # Get last N days of records
        # Used for ACWR, sleep_debt calculations
        return db.query(DailyRecord).filter(
            DailyRecord.user_id == user_id,
            DailyRecord.date >= date.today() - timedelta(days=days)
        ).order_by(DailyRecord.date.desc()).all()
```

### Database Models

#### models/user.py
```python
from sqlalchemy import Column, String, Integer, Float, DateTime
from sqlalchemy.dialects.postgresql import UUID
import uuid

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=True)
    google_id = Column(String, unique=True, nullable=True)
    full_name = Column(String, nullable=False)
    role = Column(String)  # 'athlete' or 'coach'
    age = Column(Integer, nullable=True)
    bmi = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
```

#### models/daily_record.py
```python
class DailyRecord(Base):
    __tablename__ = "daily_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    date = Column(Date, nullable=False)
    daily_distance_km = Column(Float, nullable=True)
    workout_intensity_minutes = Column(Integer, nullable=True)
    avg_cadence = Column(Integer, nullable=True)
    sleep_hours = Column(Float, nullable=True)
    hrv_score = Column(Integer, nullable=True)
    resting_hr = Column(Integer, nullable=True)
    daily_calories = Column(Integer, nullable=True)
    total_calories_burned = Column(Integer, nullable=True)
    calorie_balance = Column(Integer, nullable=True)
    stress_level = Column(Integer, nullable=True)
    muscle_soreness = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    
    __table_args__ = (UniqueConstraint('user_id', 'date'),)
```

---

## Android App Architecture

### Project Structure

```
android_app/AthleAgent/app/src/main/
├── java/com/yahav/athleagent/
│   ├── MainActivity.kt           # Entry point, navigation
│   ├── logic/
│   │   ├── LoginManager.kt       # Authentication logic
│   │   ├── ApiClient.kt          # Retrofit/OkHttp client
│   │   ├── AuthManager.kt         # JWT token storage
│   │   ├── HealthConnectManager.kt # Health Connect SDK
│   │   └── DataSyncService.kt     # Background sync
│   ├── ui/
│   │   ├── login/                # Login screens
│   │   ├── dashboard/             # Main dashboard
│   │   ├── nutrition/             # Nutrition upload
│   │   ├── survey/                # Stress survey
│   │   ├── history/               # History view
│   │   └── coach/                # Coach screens
│   ├── models/                    # Data classes
│   └── utils/                     # Utilities
└── res/
    ├── layout/                    # XML layouts
    ├── values/                    # Strings, colors
    └── drawable/                  # Images
```

### Key Files & Dependencies

#### logic/ApiClient.kt
```kotlin
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import okhttp3.OkHttpClient
import okhttp3.Interceptor

class ApiClient {
    private val baseUrl = "https://your-backend-url.com/api/"
    
    private val retrofit = Retrofit.Builder()
        .baseUrl(baseUrl)
        .client(createOkHttpClient())
        .addConverterFactory(GsonConverterFactory.create())
        .build()
    
    val apiService: ApiService = retrofit.create(ApiService::class.java)
    
    private fun createOkHttpClient(): OkHttpClient {
        return OkHttpClient.Builder()
            .addInterceptor(AuthInterceptor())
            .build()
    }
}

interface ApiService {
    @POST("auth/login")
    suspend fun login(@Body request: LoginRequest): Response<LoginResponse>
    
    @GET("predictions/today")
    suspend fun getTodayPrediction(): Response<PredictionResponse>
    
    @POST("nutrition/upload-image")
    @Multipart
    suspend fun uploadMealImage(
        @Part image: MultipartBody.Part,
        @Part mealType: String
    ): Response<NutritionResponse>
    
    // ... more endpoints
}
```

#### logic/HealthConnectManager.kt
```kotlin
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.records.*

class HealthConnectManager(private val context: Context) {
    private val healthConnectClient = HealthConnectClient.getOrCreate(context)
    
    suspend fun syncDailyData(date: LocalDate): DailyHealthData {
        // Read sleep data
        val sleepRecords = healthConnectClient.readRecords(
            ReadRecordsRequest(
                SleepSessionRecord::class,
                timeRangeFilter = TimeRangeFilter.between(
                    date.atStartOfDay(),
                    date.atTime(23, 59, 59)
                )
            )
        )
        
        // Read heart rate
        val heartRateRecords = healthConnectClient.readRecords(...)
        
        // Read steps/distance
        val stepsRecords = healthConnectClient.readRecords(...)
        
        // Aggregate and return
        return DailyHealthData(
            sleepHours = calculateSleepHours(sleepRecords),
            hrvScore = getHRV(heartRateRecords),
            restingHr = getRestingHR(heartRateRecords),
            dailyDistance = getDistance(stepsRecords),
            caloriesBurned = getCalories(stepsRecords)
        )
    }
}
```

#### ui/dashboard/DashboardActivity.kt
```kotlin
import com.yahav.athleagent.logic.ApiClient
import com.yahav.athleagent.logic.HealthConnectManager
import com.yahav.athleagent.models.Prediction

class DashboardActivity : AppCompatActivity() {
    private val apiClient = ApiClient()
    private val healthConnectManager = HealthConnectManager(this)
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_dashboard)
        
        loadTodayPrediction()
        syncHealthConnectData()
    }
    
    private suspend fun loadTodayPrediction() {
        val prediction = apiClient.apiService.getTodayPrediction()
        updatePredictionCard(prediction)
    }
    
    private suspend fun syncHealthConnectData() {
        val healthData = healthConnectManager.syncDailyData(LocalDate.now())
        // Send to backend
        apiClient.apiService.updateDailyData(healthData)
    }
}
```

### Android Dependencies (build.gradle.kts)

```kotlin
dependencies {
    // Networking
    implementation("com.squareup.retrofit2:retrofit:2.9.0")
    implementation("com.squareup.retrofit2:converter-gson:2.9.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    
    // Health Connect
    implementation("androidx.health.connect:connect-client:1.1.0-alpha07")
    
    // Google Sign-In
    implementation("com.google.android.gms:play-services-auth:20.7.0")
    
    // Image processing
    implementation("androidx.camera:camera-camera2:1.3.0")
    implementation("androidx.camera:camera-lifecycle:1.3.0")
    
    // Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")
    
    // ViewModel
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.7.0")
}
```

---

## Data Flow & Integration

### Daily Prediction Flow

```
1. User opens app (DashboardActivity)
   ↓
2. HealthConnectManager.syncDailyData()
   - Reads sleep, HR, steps from Health Connect
   - Aggregates data
   ↓
3. ApiClient.updateDailyData()
   - POST /daily-data
   - Backend saves to daily_records table
   ↓
4. Backend: PredictionService.predict_injury_risk()
   - Gets daily_record for today
   - Gets history (21 days) via DailyRecordRepository
   - MetricsService calculates ACWR, sleep_debt, hrv_drop
   - Prepares features dict
   - ModelLoader.predict() → risk_percentage
   - Saves to predictions table
   ↓
5. ApiClient.getTodayPrediction()
   - GET /predictions/today
   - Returns: { risk_percentage, risk_level, recommendations }
   ↓
6. DashboardActivity displays prediction card
```

### Nutrition Image Upload Flow

```
1. User takes photo (CameraActivity)
   ↓
2. Image saved locally
   ↓
3. ApiClient.uploadMealImage()
   - POST /nutrition/upload-image (multipart/form-data)
   ↓
4. Backend: nutrition.py route
   - Saves image to uploads/images/
   - Calls GeminiService.analyze_food_image()
   ↓
5. GeminiService
   - Converts image to base64
   - Calls Gemini API with prompt
   - Parses JSON response: { calories, protein, carbs, fats }
   ↓
6. Backend saves to nutrition_records table
   ↓
7. Aggregates daily calories → updates daily_records.daily_calories
   ↓
8. Returns nutrition data to app
```

### Team Join Flow

```
1. Coach creates team (TeamManagementActivity)
   - POST /teams { name: "Team A" }
   - Backend generates join_code (e.g., "ABC123")
   ↓
2. Athlete enters join code (JoinTeamActivity)
   - POST /teams/join { join_code: "ABC123" }
   ↓
3. Backend creates join_request (status: "pending")
   ↓
4. Coach sees pending request (CoachDashboardActivity)
   - GET /teams/{team_id}/join-requests
   ↓
5. Coach approves (ApproveRequestActivity)
   - POST /teams/{team_id}/join-requests/{request_id}/approve
   ↓
6. Backend:
   - Updates join_request.status = "approved"
   - Creates team_member record
   ↓
7. Athlete is now in team
```

---

## API Contracts

### Authentication

#### POST /auth/register
**Request:**
```json
{
  "email": "user@example.com",
  "password": "securepassword",
  "full_name": "John Doe",
  "role": "athlete"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "John Doe",
    "role": "athlete"
  }
}
```

#### POST /auth/google
**Request:**
```json
{
  "google_token": "google_oauth_token_from_android"
}
```

**Response:** Same as register

### Predictions

#### GET /predictions/today
**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "date": "2025-01-15",
  "risk_percentage": 35.7,
  "risk_level": "Medium",
  "recommendations": [
    "Reduce training intensity by 20%",
    "Increase sleep to 8+ hours",
    "Monitor HRV closely"
  ],
  "features_used": {
    "acwr_ratio": 1.35,
    "sleep_debt_3d": 4.2,
    "hrv_drop": -5.3
  }
}
```

### Daily Data

#### POST /daily-data
**Request:**
```json
{
  "date": "2025-01-15",
  "daily_distance_km": 12.5,
  "workout_intensity_minutes": 45,
  "sleep_hours": 7.5,
  "hrv_score": 65,
  "resting_hr": 52,
  "daily_calories": 2500,
  "total_calories_burned": 2800
}
```

**Response:**
```json
{
  "id": "uuid",
  "date": "2025-01-15",
  "message": "Daily data saved successfully"
}
```

### Nutrition

#### POST /nutrition/upload-image
**Content-Type:** `multipart/form-data`

**Request:**
- `image`: File (JPEG/PNG, max 10MB)
- `meal_type`: "breakfast" | "lunch" | "dinner" | "snack"
- `date`: "2025-01-15" (optional, defaults to today)

**Response:**
```json
{
  "id": "uuid",
  "date": "2025-01-15",
  "meal_type": "lunch",
  "calories": 650,
  "protein": 45.2,
  "carbs": 78.5,
  "fats": 22.1,
  "image_url": "/uploads/images/uuid.jpg"
}
```

### Teams

#### POST /teams
**Request:**
```json
{
  "name": "Team Alpha"
}
```

**Response:**
```json
{
  "id": "uuid",
  "name": "Team Alpha",
  "join_code": "ABC123",
  "coach_id": "uuid",
  "created_at": "2025-01-15T10:00:00Z"
}
```

#### POST /teams/join
**Request:**
```json
{
  "join_code": "ABC123"
}
```

**Response:**
```json
{
  "request_id": "uuid",
  "team_id": "uuid",
  "team_name": "Team Alpha",
  "status": "pending",
  "message": "Join request submitted. Waiting for coach approval."
}
```

---

## Database Schema

ראה [BACKEND_ARCHITECTURE.md](./BACKEND_ARCHITECTURE.md#database-schema-postgresql---מורחב) לפרטים מלאים.

### Key Relationships

```
users (1) ──< (many) daily_records
users (1) ──< (many) predictions
users (1) ──< (many) nutrition_records
users (1) ──< (many) stress_surveys
users (1) ──< (1) health_connect_permissions

teams (1) ──< (many) team_members
teams (1) ──< (many) join_requests
users (coach) (1) ──< (many) teams
users (athlete) (many) ──< (many) team_members ──> (1) teams
```

---

## File Dependencies & Imports

### Backend Dependencies Graph

```
main.py
  ├── api/routes/auth.py
  │     ├── services/auth_service.py
  │     │     ├── repositories/user_repository.py
  │     │     └── utils/exceptions.py
  │     └── schemas/user.py
  │
  ├── api/routes/predictions.py
  │     ├── services/prediction_service.py
  │     │     ├── ml/model_loader.py
  │     │     ├── services/metrics_service.py
  │     │     │     └── repositories/daily_record_repository.py
  │     │     └── repositories/prediction_repository.py
  │     └── schemas/prediction.py
  │
  ├── api/routes/nutrition.py
  │     ├── services/nutrition_service.py
  │     │     ├── external/gemini_service.py
  │     │     └── repositories/nutrition_repository.py
  │     └── schemas/nutrition.py
  │
  └── api/dependencies.py
        └── services/auth_service.py
```

### Key Import Chains

#### Prediction Flow
```python
# api/routes/predictions.py
from services.prediction_service import PredictionService
from ml.model_loader import ModelLoader
from services.metrics_service import MetricsService
from repositories.daily_record_repository import DailyRecordRepository

# services/prediction_service.py
from ml.model_loader import ModelLoader  # Loads injury_model.pkl
from services.metrics_service import MetricsService
from repositories.daily_record_repository import DailyRecordRepository

# services/metrics_service.py
from repositories.daily_record_repository import DailyRecordRepository
# Calculates: ACWR, sleep_debt, hrv_drop from history

# ml/model_loader.py
import joblib
# Loads: backend/injury_model.pkl
```

#### Nutrition Flow
```python
# api/routes/nutrition.py
from services.nutrition_service import NutritionService
from external.gemini_service import GeminiService

# services/nutrition_service.py
from external.gemini_service import GeminiService
from repositories.nutrition_repository import NutritionRepository

# external/gemini_service.py
import google.generativeai as genai
# Calls Gemini API with image + prompt
```

---

## Use Cases Implementation

### 1. Register

**Android:**
- `ui/login/RegisterActivity.kt`
- Calls `ApiClient.apiService.register()`

**Backend:**
- `api/routes/auth.py` → `POST /auth/register`
- `services/auth_service.py.register_user()`
- `repositories/user_repository.py.create_user()`
- Returns JWT token

### 2. Connect Health Connect

**Android:**
- `logic/HealthConnectManager.kt`
- Requests permissions via Health Connect SDK
- `ui/health/HealthConnectActivity.kt`

**Backend:**
- `api/routes/health_connect.py` → `POST /health-connect/connect`
- `services/health_connect_service.py.save_permissions()`
- Stores in `health_connect_permissions` table

### 3. Upload Meal Image

**Android:**
- `ui/nutrition/CameraActivity.kt` (takes photo)
- `logic/ApiClient.kt.uploadMealImage()` (multipart upload)

**Backend:**
- `api/routes/nutrition.py` → `POST /nutrition/upload-image`
- `services/nutrition_service.py.process_image()`
- `external/gemini_service.py.analyze_food_image()`
- Saves to `nutrition_records` table
- Updates `daily_records.daily_calories`

### 4. Fill Stress Survey

**Android:**
- `ui/survey/StressSurveyActivity.kt`
- Calls `ApiClient.apiService.submitSurvey()`

**Backend:**
- `api/routes/surveys.py` → `POST /surveys/stress`
- `repositories/survey_repository.py.create_survey()`
- Validates: one survey per day (UNIQUE constraint)
- Updates `daily_records.stress_level`

### 5. View Injury Risk

**Android:**
- `ui/dashboard/DashboardActivity.kt`
- Calls `ApiClient.apiService.getTodayPrediction()`
- Displays `PredictionCard.kt`

**Backend:**
- `api/routes/predictions.py` → `GET /predictions/today`
- `services/prediction_service.py.predict_injury_risk()`
- Returns: `{ risk_percentage, risk_level, recommendations }`

### 6. View History

**Android:**
- `ui/history/HistoryActivity.kt`
- Calls `ApiClient.apiService.getPredictionHistory(days=30)`

**Backend:**
- `api/routes/predictions.py` → `GET /predictions/history?days=30`
- `repositories/prediction_repository.py.get_history()`
- Returns array of predictions

### 7. Join Team

**Android:**
- `ui/teams/JoinTeamActivity.kt`
- User enters join code
- Calls `ApiClient.apiService.joinTeam(joinCode)`

**Backend:**
- `api/routes/teams.py` → `POST /teams/join`
- `services/team_service.py.create_join_request()`
- Creates `join_requests` record (status: "pending")

### 8. Create Team

**Android:**
- `ui/coach/TeamManagementActivity.kt` (Coach only)
- Calls `ApiClient.apiService.createTeam(name)`

**Backend:**
- `api/routes/teams.py` → `POST /teams`
- `services/team_service.py.create_team()`
- Generates unique `join_code`
- Returns team with join code

### 9. Approve Join Request

**Android:**
- `ui/coach/CoachDashboardActivity.kt`
- Shows pending requests
- Calls `ApiClient.apiService.approveJoinRequest(requestId)`

**Backend:**
- `api/routes/teams.py` → `POST /teams/{team_id}/join-requests/{request_id}/approve`
- `services/team_service.py.approve_join_request()`
- Updates `join_requests.status = "approved"`
- Creates `team_members` record

### 10. View Athlete List

**Android:**
- `ui/coach/AthleteListActivity.kt`
- Calls `ApiClient.apiService.getTeamAthletes(teamId)`

**Backend:**
- `api/routes/teams.py` → `GET /teams/{team_id}/athletes`
- `services/team_service.py.get_team_athletes()`
- Returns list of athletes in team

---

## ML Model Integration Details

### Model Training (ML_model/train_model.py)

**Input:** `athlete_injury_data.csv` (7000 samples, 21 features)

**Process:**
1. Load data
2. Split train/test (80/20)
3. Feature selection (remove weak features)
4. Train 4 models: Random Forest, XGBoost, Logistic Regression, SVM
5. Compare by F1-Score, Recall, Precision
6. Select best model (safety-focused: high recall)
7. Save to `backend/injury_model.pkl`
8. Evaluate on validation set

**Output:** `injury_model.pkl` (contains model + scaler if needed)

### Model Usage (Backend)

**File:** `backend/ml/model_loader.py`

```python
import joblib
import pandas as pd

class ModelLoader:
    def __init__(self):
        model_path = os.path.join(
            os.path.dirname(__file__), 
            '../injury_model.pkl'
        )
        loaded = joblib.load(model_path)
        self.model = loaded['model']
        self.scaler = loaded.get('scaler')  # If model needs scaling
        self.feature_names = loaded.get('feature_names')
        self.weak_features = loaded.get('weak_features', [])
    
    def predict(self, features_dict: dict) -> float:
        # Remove weak features
        for weak_feature in self.weak_features:
            features_dict.pop(weak_feature, None)
        
        # Create DataFrame with correct feature order
        df = pd.DataFrame([features_dict])
        df = df[self.feature_names]  # Ensure correct order
        
        # Scale if needed
        if self.scaler:
            df = self.scaler.transform(df)
        
        # Predict
        risk_probability = self.model.predict_proba(df)[0][1]
        return risk_probability * 100  # Convert to percentage
```

### Feature Preparation Flow

```
DailyRecord (from DB)
    ↓
MetricsService calculates:
  - acute_load_7d (from last 7 days)
  - chronic_load_21d (from last 21 days)
  - acwr_ratio = acute / chronic
  - sleep_debt_3d (from last 3 days)
  - hrv_drop = current - 7day_avg
    ↓
Features dict:
{
  "age": 25,
  "bmi": 22.5,
  "daily_distance_km": 12.5,
  "acwr_ratio": 1.35,
  "sleep_debt_3d": 4.2,
  "hrv_drop": -5.3,
  ...
}
    ↓
Remove weak features (if present):
  - stress_level
  - muscle_soreness
    ↓
ModelLoader.predict()
    ↓
risk_percentage (0-100)
```

---

## Environment Setup

### Backend (.env)

> **נוכחי:** הבקאנד נשען על **Firestore** לנתוני אפליקציה ול-persist תוצאות חיזוי. אין `DATABASE_URL` ל-PostgreSQL ביישום זה. הגדרו אישורי Firebase Admin (למשל `FIREBASE_SERVICE_ACCOUNT_KEY` או `GOOGLE_APPLICATION_CREDENTIALS`).

```env
# Firebase Admin / Firestore (קריאה וכתיבת תוצאות חיזוי)
FIREBASE_SERVICE_ACCOUNT_KEY=/path/to/service-account.json

# Google OAuth (אופציונלי — עזרי אימות טוקן אם בשימוש)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Gemini AI (אופציונלי — לרוב בצד האפליקציה)
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-1.5-pro

# File Uploads
UPLOAD_DIR=./uploads/images
MAX_UPLOAD_SIZE=10485760
```

### Android (local.properties)

```properties
# Backend API URL
API_BASE_URL=https://your-backend-url.com/api/

# Google Sign-In
GOOGLE_CLIENT_ID=your-android-google-client-id
```

---

## Testing Strategy

### Backend Tests

1. **Unit Tests**: Services, repositories (mock DB)
2. **Integration Tests**: API endpoints (test client)
3. **ML Tests**: Model prediction accuracy on validation set

### Android Tests

1. **Unit Tests**: ViewModels, business logic
2. **Instrumented Tests**: UI flows, API calls
3. **Health Connect Tests**: Mock Health Connect data

---

## Deployment

### Backend

1. **Data store**: Firestore (production) — אין PostgreSQL ביישום הנוכחי
2. **Server**: FastAPI with Uvicorn
3. **Model**: artifact path configured via `MODEL_PATH` / promoted manifest (see `backend/ml/model_loader.py`)
4. **Environment**: Load from `.env` or environment variables

### Android

1. **Build**: APK/AAB via Gradle
2. **Health Connect**: Requires Android 14+ or Health Connect app
3. **Permissions**: Camera, Health Connect, Internet

---

## Next Steps

1. ✅ Complete backend implementation (all phases)
2. ✅ Implement Android app screens
3. ✅ Integrate Health Connect
4. ✅ Test Gemini API integration
5. ✅ Deploy backend to production
6. ✅ Publish Android app to Play Store

---

## Notes

- **Model Updates**: Retrain model periodically with new data
- **Feature Engineering**: ACWR, sleep_debt calculated on-the-fly (not stored)
- **Weak Features**: Automatically removed during training, handled in prediction
- **History Requirements**: Need 21 days of data for accurate ACWR calculation
- **Fallbacks**: Manual entry if Gemini/Health Connect fails

