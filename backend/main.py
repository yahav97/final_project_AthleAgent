"""
AthleAgent FastAPI Backend
Main application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import joblib
import pandas as pd
import os

from config import settings
from utils.logging import logger

# Import all models to register them
from models import (
    User, Team, TeamMember, JoinRequest,
    DailyRecord, Prediction, NutritionRecord,
    StressSurvey, HealthConnectPermission, Injury
)

# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Smart injury risk prediction system using ML"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load the model (From your working version)
script_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(script_dir, 'injury_model.pkl')
model = None

if os.path.exists(model_path):
    model = joblib.load(model_path)
    logger.info("Model loaded successfully!")
else:
    logger.warning(f"Model file not found at {model_path}. Please run train_model.py first.")

@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info("Database models loaded")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down server")


class AthleteData(BaseModel):
    age: int
    bmi: float
    history_injury_count: int
    vo2_max: int
    daily_distance_km: float
    workout_intensity_minutes: int
    avg_cadence: int
    sleep_hours: float
    hrv_score: int
    resting_hr: int
    daily_calories: int
    total_calories_burned: int
    calorie_balance: int
    stress_level: int
    muscle_soreness: int
    acute_load_7d: float
    chronic_load_21d: float
    acwr_ratio: float
    sleep_debt_3d: float
    hrv_drop: float

class SimpleData(BaseModel):
    user_id: str

@app.get("/")
async def root():
    """Root endpoint - health check."""
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# ----------------------------------
# ML Prediction Endpoints
# ----------------------------------

@app.post("/test_predict")
def test_predict_injury(data: SimpleData):
    return {
        "user_id": data.user_id,
        "risk_percentage": 72.5,
        "risk_level": "High",
        "message": "This is a mock response for Android UI testing"
    }

@app.post("/demo_predict")
def demo_predict_injury(data: AthleteData):

    score = 10.0
    
    if data.sleep_hours < 5.0:
        score += 30.0
    elif data.sleep_hours < 7.0:
        score += 15.0
        
    score += (data.muscle_soreness * 7.0)
    score += (data.stress_level * 0.25)
    
    if data.daily_distance_km > 12.0:
        score += 15.0

    final_score = min(score, 100.0)
    
    return {
        "risk_percentage": round(final_score, 1),
        "risk_level": "High" if final_score > 60 else "Medium" if final_score > 40 else "Low"
    }

@app.post("/predict")
def predict_injury(data: AthleteData):
    if model is None:
        return {"error": "Model not loaded"}
    
    input_df = pd.DataFrame([data.model_dump()])
    risk_probability = model.predict_proba(input_df)[0][1]
    
    return {
        "risk_percentage": round(risk_probability * 100, 1),
        "risk_level": "High" if risk_probability > 0.6 else "Medium" if risk_probability > 0.3 else "Low"
    }

# ----------------------------------

# Import and register API routes
from api.routes import auth

# Register authentication routes
app.include_router(
    auth.router,
    prefix=settings.API_V1_PREFIX + "/auth",
    tags=["Authentication"],
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="warning",
    )