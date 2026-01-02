---
name: Complete Backend with Teams, Health Connect, Nutrition API
overview: "בניית backend מלא לפי מסמך הדרישות: Teams/Groups, Health Connect integration, Nutrition API, Stress Surveys, Coach features, וכל ה-Use Cases המפורטים"
todos:
  - id: db_setup
    content: Set up PostgreSQL database and create complete schema (users, teams, daily_records, predictions, nutrition, surveys, health_connect)
    status: pending
  - id: core_infrastructure
    content: "Create core infrastructure: database connection, config management, logging, error handling"
    status: pending
    dependencies:
      - db_setup
  - id: auth_system
    content: "Implement authentication: JWT, password hashing, Google OAuth, user roles (Athlete/Coach)"
    status: pending
    dependencies:
      - core_infrastructure
  - id: team_management
    content: "Implement team management: create teams, join codes, join requests, approval workflow"
    status: pending
    dependencies:
      - auth_system
  - id: data_models
    content: Create all SQLAlchemy models and Pydantic schemas (User, Team, DailyRecord, Prediction, Nutrition, Survey)
    status: pending
    dependencies:
      - db_setup
  - id: repositories
    content: Implement all repositories for data access (user, team, daily_record, prediction, nutrition, survey)
    status: pending
    dependencies:
      - data_models
  - id: metrics_service
    content: "Create MetricsService: Calculate ACWR, sleep_debt, hrv_drop from historical daily_records"
    status: pending
    dependencies:
      - repositories
  - id: external_apis
    content: "Implement external API integrations: Gemini AI service for nutrition analysis, Health Connect service"
    status: pending
    dependencies:
      - repositories
  - id: prediction_service
    content: "Create PredictionService: Load ML model, prepare features, calculate predictions, generate recommendations"
    status: pending
    dependencies:
      - metrics_service
  - id: api_routes
    content: "Implement all API routes: auth, teams, daily-data, predictions, nutrition, surveys, health-connect, coach endpoints"
    status: pending
    dependencies:
      - prediction_service
      - external_apis
      - team_management
  - id: testing
    content: Test all endpoints, team workflows, external API integrations, ML predictions, role-based access
    status: pending
    dependencies:
      - api_routes
---

# Complete Backend Architecture - AthleAgent

## מבנה הפרויקט (מורחב)

```
backend/
├── main.py                 # FastAPI app entry point
├── config.py              # Configuration (DB, secrets, APIs)
├── database/
│   ├── __init__.py
│   ├── connection.py      # PostgreSQL connection pool
│   └── migrations/        # Alembic migrations
├── models/
│   ├── __init__.py
│   ├── user.py           # User model (Athlete/Coach)
│   ├── team.py           # Team model
│   ├── team_member.py    # Team membership
│   ├── join_request.py   # Join team requests
│   ├── daily_record.py   # Daily metrics
│   ├── prediction.py     # Prediction history
│   ├── nutrition_record.py # Nutrition data (from API)
│   ├── stress_survey.py  # Daily stress surveys
│   └── health_connect.py # Health Connect permissions
├── schemas/
│   ├── __init__.py
│   ├── user.py
│   ├── team.py
│   ├── daily_record.py
│   ├── prediction.py
│   ├── nutrition.py
│   └── survey.py
├── repositories/
│   ├── __init__.py
│   ├── user_repository.py
│   ├── team_repository.py
│   ├── daily_record_repository.py
│   ├── prediction_repository.py
│   ├── nutrition_repository.py
│   └── survey_repository.py
├── services/
│   ├── __init__.py
│   ├── auth_service.py
│   ├── prediction_service.py
│   ├── metrics_service.py
│   ├── team_service.py
│   ├── nutrition_service.py  # Nutrition API integration
│   └── health_connect_service.py # Health Connect sync
├── api/
│   ├── __init__.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── teams.py       # Team management
│   │   ├── daily_data.py
│   │   ├── predictions.py
│   │   ├── nutrition.py   # Upload meal image
│   │   ├── surveys.py     # Stress level survey
│   │   └── health_connect.py # Health Connect connection
│   └── dependencies.py
├── ml/
│   ├── __init__.py
│   └── model_loader.py
├── external/
│   ├── __init__.py
│   ├── gemini_service.py  # Google Gemini API for nutrition analysis
│   └── health_connect.py # Health Connect API client
└── utils/
    ├── __init__.py
    ├── logging.py
    └── exceptions.py
```

## Database Schema (PostgreSQL) - מורחב

### 1. users
```sql
- id (UUID, PK)
- email (VARCHAR, UNIQUE, NOT NULL)
- password_hash (VARCHAR, nullable)
- google_id (VARCHAR, nullable, UNIQUE)
- full_name (VARCHAR, NOT NULL)
- role (VARCHAR) -- 'athlete' or 'coach'
- age (INTEGER, nullable)
- bmi (FLOAT, nullable)
- vo2_max (INTEGER, nullable)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
```

### 2. teams
```sql
- id (UUID, PK)
- name (VARCHAR, UNIQUE, NOT NULL)
- coach_id (UUID, FK -> users.id, NOT NULL)
- join_code (VARCHAR, UNIQUE, NOT NULL) -- 6-8 character code
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
```

### 3. team_members
```sql
- id (UUID, PK)
- team_id (UUID, FK -> teams.id, NOT NULL)
- athlete_id (UUID, FK -> users.id, NOT NULL)
- joined_at (TIMESTAMP)
- UNIQUE(team_id, athlete_id)
```

### 4. join_requests
```sql
- id (UUID, PK)
- team_id (UUID, FK -> teams.id, NOT NULL)
- athlete_id (UUID, FK -> users.id, NOT NULL)
- status (VARCHAR) -- 'pending', 'approved', 'rejected'
- requested_at (TIMESTAMP)
- UNIQUE(team_id, athlete_id) -- One pending request per team
```

### 5. daily_records
```sql
- id (UUID, PK)
- user_id (UUID, FK -> users.id, NOT NULL)
- date (DATE, NOT NULL)
- daily_distance_km (FLOAT, nullable)
- workout_intensity_minutes (INTEGER, nullable)
- avg_cadence (INTEGER, nullable)
- sleep_hours (FLOAT, nullable) -- From Health Connect
- hrv_score (INTEGER, nullable) -- From Health Connect
- resting_hr (INTEGER, nullable) -- From Health Connect
- daily_calories (INTEGER, nullable) -- From Nutrition API
- total_calories_burned (INTEGER, nullable) -- From Health Connect
- calorie_balance (INTEGER, nullable) -- Calculated
- stress_level (INTEGER, nullable) -- From survey
- muscle_soreness (INTEGER, nullable) -- Optional
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
- UNIQUE(user_id, date)
```

### 6. predictions
```sql
- id (UUID, PK)
- user_id (UUID, FK -> users.id, NOT NULL)
- date (DATE, NOT NULL)
- risk_percentage (FLOAT) -- 0-100
- risk_level (VARCHAR) -- 'Low', 'Medium', 'High'
- features_used (JSONB) -- Store features used
- recommendations (TEXT, nullable) -- Generated recommendations
- created_at (TIMESTAMP)
- UNIQUE(user_id, date)
```

### 7. nutrition_records
```sql
- id (UUID, PK)
- user_id (UUID, FK -> users.id, NOT NULL)
- date (DATE, NOT NULL)
- meal_type (VARCHAR) -- 'breakfast', 'lunch', 'dinner', 'snack'
- image_url (VARCHAR, nullable) -- Stored image path
- calories (INTEGER, nullable) -- From Gemini AI
- protein (FLOAT, nullable)
- carbs (FLOAT, nullable)
- fats (FLOAT, nullable)
- gemini_response (JSONB, nullable) -- Full Gemini API response
- manual_entry (BOOLEAN) -- True if user entered manually
- created_at (TIMESTAMP)
```

### 8. stress_surveys
```sql
- id (UUID, PK)
- user_id (UUID, FK -> users.id, NOT NULL)
- date (DATE, NOT NULL)
- stress_level (INTEGER) -- 1-10
- mood_score (INTEGER, nullable) -- 1-10
- energy_level (INTEGER, nullable) -- 1-10
- sleep_quality (INTEGER, nullable) -- 1-10
- additional_notes (TEXT, nullable)
- created_at (TIMESTAMP)
- UNIQUE(user_id, date) -- One survey per day
```

### 9. health_connect_permissions
```sql
- id (UUID, PK)
- user_id (UUID, FK -> users.id, UNIQUE, NOT NULL)
- is_connected (BOOLEAN, DEFAULT FALSE)
- permissions_granted (JSONB) -- Which permissions user granted
- last_sync_at (TIMESTAMP, nullable)
- created_at (TIMESTAMP)
```

### 10. injuries (optional - for tracking)
```sql
- id (UUID, PK)
- user_id (UUID, FK -> users.id, NOT NULL)
- date (DATE, NOT NULL)
- injury_type (VARCHAR)
- severity (VARCHAR) -- 'mild', 'moderate', 'severe'
- body_part (VARCHAR)
- notes (TEXT, nullable)
- created_at (TIMESTAMP)
```

## API Endpoints - לפי Use Cases

### Authentication
- `POST /auth/register` - Register (email/password or Google)
- `POST /auth/login` - Login (email/password)
- `POST /auth/google` - Google OAuth token exchange
- `GET /auth/me` - Get current user info
- `POST /auth/logout` - Logout

### Teams (Coach Features)
- `POST /teams` - Create team (Coach only)
- `GET /teams/my-teams` - Get user's teams
- `GET /teams/{team_id}` - Get team details
- `GET /teams/{team_id}/athletes` - Get athletes in team (Coach)
- `POST /teams/join` - Join team by code (Athlete)
- `GET /teams/{team_id}/join-requests` - Get pending requests (Coach)
- `POST /teams/{team_id}/join-requests/{request_id}/approve` - Approve request (Coach)
- `POST /teams/{team_id}/join-requests/{request_id}/reject` - Reject request (Coach)

### Health Connect
- `POST /health-connect/connect` - Connect Health Connect account
- `GET /health-connect/status` - Check connection status
- `POST /health-connect/sync` - Manual sync from Health Connect
- `DELETE /health-connect/disconnect` - Disconnect Health Connect

### Nutrition
- `POST /nutrition/upload-image` - Upload meal image (multipart/form-data)
- `POST /nutrition/manual-entry` - Manual nutrition entry (if API fails)
- `GET /nutrition/today` - Get today's nutrition records
- `GET /nutrition/history?days=30` - Get nutrition history

### Stress Survey
- `POST /surveys/stress` - Submit stress survey (one per day)
- `GET /surveys/today` - Get today's survey
- `GET /surveys/history?days=30` - Get survey history
- `PUT /surveys/today` - Update today's survey (if not submitted)

### Daily Data
- `POST /daily-data` - Submit/update daily metrics
- `GET /daily-data/today` - Get today's data
- `GET /daily-data/history?days=30` - Get historical data
- `GET /daily-data/date/{date}` - Get data for specific date

### Predictions
- `GET /predictions/today` - Get today's injury risk prediction
- `GET /predictions/history?days=30` - Get prediction history
- `GET /predictions/date/{date}` - Get prediction for specific date
- `GET /predictions/recommendations` - Get recommendations based on risk

### Coach - View Athletes
- `GET /coach/athletes` - Get all athletes in coach's teams
- `GET /coach/athletes/{athlete_id}/predictions` - View athlete's predictions
- `GET /coach/athletes/{athlete_id}/history` - View athlete's history

## Implementation Phases

### Phase 1: Database & Core Infrastructure
1. PostgreSQL setup
2. SQLAlchemy models (all tables)
3. Alembic migrations
4. Database connection pool
5. Config management
6. Logging & error handling

### Phase 2: Authentication System
1. JWT token generation/validation
2. Password hashing (bcrypt)
3. Google OAuth integration
4. User roles (Athlete/Coach)
5. Auth dependencies

### Phase 3: User & Team Management
1. User repository & service
2. Team repository & service
3. Join request logic
4. Team endpoints (create, join, approve)
5. Role-based access control

### Phase 4: Daily Data & Metrics
1. DailyRecord model & repository
2. MetricsService (ACWR, sleep_debt, hrv_drop calculations)
3. Daily data endpoints
4. History queries (optimized for rolling averages)

### Phase 5: External Integrations
1. **Health Connect Service**
   - Permission management
   - Data sync logic
   - Health Connect API client
2. **Gemini AI Service (Nutrition Analysis)**
   - Google Gemini API integration (google-generativeai)
   - Image processing (base64 encoding or file upload)
   - Prompt engineering for food analysis (structured JSON response)
   - Parse Gemini response to extract nutrition values
   - Error handling and fallback to manual entry
   - Image storage (local filesystem)

### Phase 6: Surveys & Additional Data
1. StressSurvey model & repository
2. Survey endpoints (submit, get, history)
3. Validation (one survey per day)

### Phase 7: ML Integration & Predictions
1. Model loader (injury_model.pkl)
2. Feature preparation (handle weak features)
3. PredictionService (calculate from daily data)
4. Prediction endpoints
5. Recommendations generation

### Phase 8: Coach Features
1. Coach endpoints (view athletes, predictions, history)
2. Team-based filtering
3. Permissions (coach can only see their team athletes)

### Phase 9: Testing & Validation
1. Test all endpoints
2. Test team workflows
3. Test external API integrations
4. Test ML predictions
5. Test role-based access

## Key Technical Decisions

1. **Team Join Code**: Generate unique 6-8 character codes (alphanumeric)
2. **Health Connect Sync**: Store permissions, sync on-demand or scheduled
3. **Nutrition API**: Store images locally, call API async, fallback to manual entry
4. **Survey Validation**: One survey per day per user (enforced at DB level)
5. **Role-Based Access**: Coach can only access their team's athletes
6. **Daily Data Aggregation**: Combine data from Health Connect, Nutrition API, and Surveys into daily_records
7. **Prediction Calculation**: Triggered automatically when daily data is complete, or on-demand

## External API Integrations

### Google Gemini API (Nutrition Analysis)

- **Service**: Google Gemini (gemini-pro-vision or gemini-1.5-pro)
- **Method**: POST with image (base64 encoded or file)
- **Prompt**: Structured prompt to extract calories, protein, carbs, fats
- **Response**: JSON with nutrition data
- **Error Handling**: Fallback to manual entry if Gemini fails/unavailable
- **Image Format**: JPEG/PNG, max 10MB

### Health Connect (Android)

- **Integration**: Android Health Connect SDK
- **Data Sync**: Pull data from Health Connect on sync request
- **Permissions**: Sleep, Heart Rate, Steps/Distance, Calories
- **Storage**: Store in daily_records table

## Dependencies

```python
# requirements.txt
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
sqlalchemy>=2.0.0
alembic>=1.12.0
psycopg2-binary>=2.9.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
python-multipart>=0.0.6
google-auth>=2.23.0
google-generativeai>=0.3.0  # Gemini API
pydantic[email]>=2.5.0
python-dotenv>=1.0.0
pillow>=10.0.0  # Image processing
httpx>=0.25.0   # HTTP client for external APIs
```

## Environment Variables

```env
DATABASE_URL=postgresql://user:password@localhost:5432/athleagent
SECRET_KEY=your-secret-key-for-jwt
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-1.5-pro  # or gemini-pro-vision
UPLOAD_DIR=./uploads/images
MAX_UPLOAD_SIZE=10485760  # 10MB
```

## Use Cases Implementation Mapping

| Use Case | Endpoints | Services |
|----------|-----------|----------|
| Register | POST /auth/register, POST /auth/google | AuthService |
| Connect Health Connect | POST /health-connect/connect | HealthConnectService |
| Upload Meal Image | POST /nutrition/upload-image | GeminiService (analyzes image) |
| Fill Stress Survey | POST /surveys/stress | SurveyService |
| View Injury Risk | GET /predictions/today | PredictionService |
| View History | GET /predictions/history, GET /daily-data/history | PredictionService, DailyRecordRepository |
| Join Team | POST /teams/join | TeamService |
| Create Team | POST /teams | TeamService |
| Approve Join Request | POST /teams/{id}/join-requests/{id}/approve | TeamService |
| View Athlete List | GET /teams/{id}/athletes | TeamService |

## Gemini AI Integration Details

### Prompt Template for Nutrition Analysis

```
Analyze this food image and extract the following nutritional information:
- Total calories (integer)
- Protein in grams (float)
- Carbohydrates in grams (float)
- Fats in grams (float)

Return the response as a JSON object with exactly these fields:
{
  "calories": <integer>,
  "protein": <float>,
  "carbs": <float>,
  "fats": <float>
}

If you cannot identify the food or estimate the values, return null for that field.
```

### Implementation Notes

1. **Image Processing**: Convert uploaded image to base64 or use file path
2. **Gemini API Call**: Use `google-generativeai` library
3. **Response Parsing**: Extract JSON from Gemini's text response
4. **Error Handling**: If Gemini fails, allow manual entry
5. **Caching**: Consider caching similar images (optional)

## Next Steps

1. Get Gemini API key from Google AI Studio
2. Set up Health Connect integration details
3. Implement image storage solution
4. Test Gemini prompt and response parsing
5. Add notification system for high-risk predictions
6. Add data export features for coaches

