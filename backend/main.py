from fastapi import FastAPI
from pydantic import BaseModel
import joblib
import pandas as pd
import os

app = FastAPI()

# Load the model
script_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(script_dir, 'injury_model.pkl')
model = None

if os.path.exists(model_path):
    model = joblib.load(model_path)
    print("Model loaded successfully!")
else:
    print(f"WARNING: Model file not found at {model_path}. Please run train_model.py first.")

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

@app.get("/")
def read_root():
    return {"status": "Server is running"}

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