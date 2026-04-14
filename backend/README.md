# Backend - AthleAgent API

FastAPI backend for AthleAgent injury prediction system.

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r ../requirements.txt
```

### 2. Setup Database

1. Create PostgreSQL database `athleagent` in pgAdmin
2. Update `config.py` with your database credentials
3. Run:

```bash
python create_tables.py
```

### 3. Run Server

```bash
uvicorn main:app --reload
```

Server runs on: `http://localhost:8000`
API Docs: `http://localhost:8000/docs`

## 📁 Project Structure

```
backend/
├── main.py              # FastAPI app entry point
├── config.py            # Configuration (env variables)
├── create_tables.py     # Database initialization script
│
├── models/              # SQLAlchemy ORM models
│   ├── user.py
│   ├── daily_record.py
│   ├── prediction.py
│   └── ...
│
├── schemas/             # Pydantic validation schemas
│   ├── user.py
│   ├── daily_data.py
│   └── ...
│
├── repositories/        # Data access layer
│   ├── user_repository.py
│   └── ...
│
├── services/            # Business logic
│   ├── auth_service.py
│   ├── prediction_service.py
│   └── ...
│
├── api/                 # API routes
│   └── routes/
│       ├── auth.py
│       ├── predictions.py
│       └── ...
│
├── database/            # Database connection
│   └── connection.py
│
├── utils/               # Utilities
│   ├── logging.py
│   └── exceptions.py
│
└── ml/                  # ML model integration
    └── model_loader.py
```

## 🔧 Configuration

Create `.env` file:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/athleagent
SECRET_KEY=your-secret-key-min-32-chars
GEMINI_API_KEY=your-gemini-api-key
```

## 📊 Database Models

- **User** - Users (athletes/coaches)
- **DailyRecord** - Daily training/health data
- **Prediction** - Injury risk predictions
- **NutritionRecord** - Meal data from Gemini AI
- **StressSurvey** - Daily stress surveys
- **Team** - Team management
- **HealthConnectPermission** - Health Connect integration

## 🧪 Testing

```bash
# Test database connection
python create_tables.py

# Run with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 📝 API Documentation

Once server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

