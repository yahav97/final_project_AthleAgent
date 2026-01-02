# AthleAgent - Smart Injury Risk Prediction System

מערכת חכמה למעקב וחיזוי סיכון לפציעות בעזרת מודל למידת מכונה.

## 🏗️ ארכיטקטורה

```
┌─────────────────┐
│  Android App    │  (Kotlin)
│  (Frontend)     │
└────────┬────────┘
         │ HTTP/REST API
         │ JWT Authentication
         ▼
┌─────────────────┐
│  FastAPI        │  (Python)
│  Backend        │
└────────┬────────┘
         │
    ┌────┴────┬──────────────┬─────────────┐
    │         │              │             │
    ▼         ▼              ▼             ▼
┌────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│PostgreSQL│ │Gemini AI│ │Health    │ │ML Model  │
│Database  │ │(Nutrition)│ │Connect   │ │(XGBoost/ │
│          │ │          │ │(Android) │ │RF/SVM)   │
└──────────┘ └──────────┘ └──────────┘ └──────────┘
```

## 📁 מבנה הפרויקט

```
final_project_AthleAgent/
├── backend/              # Python FastAPI Backend
│   ├── models/          # SQLAlchemy database models
│   ├── schemas/         # Pydantic validation schemas
│   ├── repositories/    # Data access layer
│   ├── services/        # Business logic
│   ├── api/            # API routes/endpoints
│   ├── ml/             # ML model integration
│   ├── database/       # Database connection
│   └── utils/          # Utilities (logging, exceptions)
│
├── ML_model/           # ML Model Training
│   ├── data_generator.py
│   ├── train_model.py
│   └── athlete_injury_data.csv
│
├── android_app/        # Android App (Kotlin)
│   └── AthleAgent/
│
└── docs/              # Documentation
    ├── COMPLETE_PROJECT_ARCHITECTURE.md
    └── BACKEND_ARCHITECTURE.md
```

## 🚀 התחלה מהירה

### Backend Setup

1. **התקנת תלויות:**
```bash
cd backend
pip install -r ../requirements.txt
```

2. **הגדרת Database:**
- פתחי pgAdmin
- צרי database חדש: `athleagent`
- עדכני את `backend/config.py` עם פרטי החיבור שלך

3. **יצירת Tables:**
```bash
python create_tables.py
```

4. **הרצת השרת:**
```bash
uvicorn main:app --reload
```

השרת יעלה על: `http://localhost:8000`
API Documentation: `http://localhost:8000/docs`

### ML Model Training

```bash
cd ML_model
python data_generator.py  # יוצר נתונים
python train_model.py     # מאמן את המודל
```

המודל נשמר ב: `backend/injury_model.pkl`

## 📊 Database Schema

- **users** - משתמשים (athletes ו-coaches)
- **teams** - קבוצות
- **daily_records** - נתונים יומיים (אימונים, שינה, HR)
- **predictions** - ניבויי פציעות יומיים
- **nutrition_records** - תזונה (מ-Gemini AI)
- **stress_surveys** - סקרי לחץ
- **health_connect_permissions** - הרשאות Health Connect

ראה [COMPLETE_PROJECT_ARCHITECTURE.md](docs/COMPLETE_PROJECT_ARCHITECTURE.md) לפרטים מלאים.

## 🔧 טכנולוגיות

### Backend
- **FastAPI** - Web framework
- **PostgreSQL** - Database
- **SQLAlchemy** - ORM
- **Pydantic** - Data validation
- **JWT** - Authentication
- **Google Gemini AI** - Nutrition analysis

### ML
- **scikit-learn** - ML models
- **XGBoost** - Gradient boosting
- **pandas** - Data processing

### Android
- **Kotlin** - Programming language
- **Health Connect** - Health data sync
- **Retrofit** - HTTP client

## 📝 API Endpoints

### Authentication
- `POST /auth/register` - הרשמה
- `POST /auth/login` - התחברות
- `POST /auth/google` - התחברות עם Google

### Predictions
- `GET /predictions/today` - ניבוי יומי
- `GET /predictions/history` - היסטוריה

### Daily Data
- `POST /daily-data` - עדכון נתונים יומיים
- `GET /daily-data/today` - נתונים יומיים

ראה [API Contracts](docs/COMPLETE_PROJECT_ARCHITECTURE.md#api-contracts) לפרטים מלאים.

## 🔐 Environment Variables

צרי קובץ `backend/.env`:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/athleagent
SECRET_KEY=your-secret-key-min-32-chars
GEMINI_API_KEY=your-gemini-api-key
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

## 📚 תיעוד

- [Complete Project Architecture](docs/COMPLETE_PROJECT_ARCHITECTURE.md)
- [Backend Architecture](docs/BACKEND_ARCHITECTURE.md)

## 👥 צוות

- [שם משתמש 1]
- [שם משתמש 2]

## 📄 רישיון

[ציין רישיון]

