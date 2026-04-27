"""
AthleAgent - Synthetic Data Generator for Injury Prediction

This script generates synthetic athlete data for training the injury prediction model.
The data generation is based on sports science research and realistic athlete metrics.

Key Features:
- Physical load metrics (distance, intensity, ACWR)
- Physiological recovery (sleep, HRV, resting HR)
- Nutrition (calories, energy balance)
- Mental state (stress, muscle soreness)

Injury Risk Calculation:
Based on research-validated risk factors:
- ACWR > 1.4: High acute-to-chronic workload ratio (Gabbett, 2016)
- Sleep debt > 5 hours: Cumulative sleep deprivation
- HRV drop < -8: Significant autonomic nervous system stress
- High stress levels: Psychological stress impact
- Injury history: Previous injury as risk factor

Author: AthleAgent Project
"""

import argparse
import os

import numpy as np
import pandas as pd

# ============================================================================
# CONFIGURATION
# ============================================================================

NUM_ATHLETES = 1000         # Default requested scale for first iteration
DAYS_PER_ATHLETE = 365      # One full year per athlete
START_DATE = '2025-01-01'   # Starting date for data generation
DEFAULT_SEED = 42

# ============================================================================
# DATA GENERATION FUNCTION
# ============================================================================

def generate_synthetic_data(
    num_athletes: int = NUM_ATHLETES,
    days_per_athlete: int = DAYS_PER_ATHLETE,
    seed: int = DEFAULT_SEED,
):
    np.random.seed(seed)
    all_data = []
    print(
        f"Generating data for {num_athletes} athletes over {days_per_athlete} days "
        f"(seed={seed})..."
    )

    for athlete_id in range(1, num_athletes + 1):
        # Generate athlete baseline characteristics (constant per athlete)
        age = np.random.randint(18, 40)
        height = np.random.normal(1.75, 0.10)  # Average height ~175cm
        weight = np.random.normal(75, 10)      # Average weight ~75kg
        bmi = round(weight / (height ** 2), 2)
        vo2_max = np.random.randint(40, 65)   # VO2 max in ml/kg/min
        # Injury history: 60% no injuries, 20% 1 injury, 10% 2, 10% 3+
        history_injury_count = np.random.choice([0, 1, 2, 3], p=[0.6, 0.2, 0.1, 0.1])
        base_hrv = np.random.randint(40, 90)  # Baseline HRV (ms)
        base_resting_hr = np.random.randint(45, 65)  # Baseline resting HR (bpm)
        dates = pd.date_range(start=START_DATE, periods=days_per_athlete)
        
        for day in range(days_per_athlete):
            # ============================================================
            # PHYSICAL LOAD METRICS
            # ============================================================
            # Daily training distance (km) - Gamma distribution for realistic training patterns
            daily_distance = np.random.gamma(shape=2, scale=3)
            if daily_distance < 1: daily_distance = 0  # Rest days
            
            # Workout intensity (minutes) - correlated with distance
            workout_intensity = int(daily_distance * np.random.randint(4, 7)) if daily_distance > 0 else 0
            
            # Average cadence (steps/min) - typical running cadence ~170
            avg_cadence = np.random.normal(170, 5) if daily_distance > 0 else 0
            
            # ============================================================
            # SLEEP AND RECOVERY METRICS
            # ============================================================
            # Sleep hours - normal distribution around 7 hours, bounded 3-10
            sleep_hours = max(3, min(10, np.random.normal(7, 1.5)))
            
            # HRV (Heart Rate Variability) - affected by sleep quality
            hrv_fluctuation = np.random.normal(0, 5)
            if sleep_hours < 5:  # Poor sleep reduces HRV
                hrv_fluctuation -= 10
            hrv_score = int(base_hrv + hrv_fluctuation)
            
            # Resting heart rate - slight daily variation
            resting_hr = int(base_resting_hr + (np.random.normal(0, 2)))
            
            # ============================================================
            # NUTRITION METRICS
            # ============================================================
            # Daily calorie intake
            daily_calories = int(np.random.normal(2500, 300))
            
            # Calorie burn calculation
            active_burn = int(daily_distance * 60)  # ~60 cal/km
            # BMR (Basal Metabolic Rate) - Mifflin-St Jeor equation
            bmr = int(10 * weight + 6.25 * (height*100) - 5 * age + 5)
            total_burned = bmr + active_burn
            
            # ============================================================
            # SUBJECTIVE METRICS
            # ============================================================
            # Stress level (1-10 scale)
            stress_level = np.random.randint(1, 11)
            
            # Muscle soreness (1-10 scale) - increases with high training load
            muscle_soreness = np.random.randint(1, 11)
            if daily_distance > 10:  # High training load increases soreness
                muscle_soreness += 2

            row = {
                'athlete_id': athlete_id, 'date': dates[day], 'age': age, 'bmi': bmi,
                'history_injury_count': history_injury_count, 'vo2_max': vo2_max,
                'daily_distance_km': round(daily_distance, 2),
                'workout_intensity_minutes': workout_intensity, 'avg_cadence': int(avg_cadence),
                'sleep_hours': round(sleep_hours, 1), 'hrv_score': hrv_score, 'resting_hr': resting_hr,
                'daily_calories': daily_calories, 'total_calories_burned': total_burned,
                'stress_level': stress_level, 'muscle_soreness': min(10, muscle_soreness)
            }
            all_data.append(row)

    df = pd.DataFrame(all_data)
    
    # ============================================================================
    # FEATURE ENGINEERING
    # ============================================================================
    
    # ACWR (Acute:Chronic Workload Ratio) - Key injury risk indicator
    # Acute load: 7-day rolling average
    df['acute_load_7d'] = df.groupby('athlete_id')['daily_distance_km'].transform(
        lambda x: x.rolling(7).mean()
    )
    # Chronic load: 21-day rolling average
    df['chronic_load_21d'] = df.groupby('athlete_id')['daily_distance_km'].transform(
        lambda x: x.rolling(21).mean()
    )
    # ACWR ratio - Research shows >1.4 indicates high injury risk (Gabbett, 2016)
    df['acwr_ratio'] = df['acute_load_7d'] / df['chronic_load_21d'].replace(0, np.nan)
    df['acwr_ratio'] = df['acwr_ratio'].fillna(1.0)  # Handle division by zero
    
    # Energy balance (calories in - calories out)
    df['calorie_balance'] = df['daily_calories'] - df['total_calories_burned']
    
    # Sleep debt - cumulative sleep deficit over 3 days (assuming 8h ideal)
    df['sleep_debt_3d'] = df.groupby('athlete_id')['sleep_hours'].transform(
        lambda x: (8 - x).rolling(3).sum()
    )
    
    # HRV rolling average (7-day baseline)
    df['hrv_rolling_7d'] = df.groupby('athlete_id')['hrv_score'].transform(
        lambda x: x.rolling(7).mean()
    )
    # HRV drop - negative values indicate stress/recovery issues
    df['hrv_drop'] = df['hrv_score'] - df['hrv_rolling_7d']

    # ============================================================================
    # INJURY RISK CALCULATION
    # ============================================================================
    # Based on research-validated risk factors
    # Risk is cumulative - multiple factors increase probability
    def calculate_injury_risk(row):
        base_risk = 0.05  # Base injury probability (5%)
        risk = base_risk  # Initialize risk with base value
        
        # ACWR > 1.4: High acute-to-chronic workload (Gabbett, 2016)
        # This is the strongest predictor - adds 35% risk
        if row['acwr_ratio'] > 1.4:
            risk += 0.35
        
        # Sleep debt > 5 hours: Significant sleep deprivation
        # Impacts recovery and increases injury risk
        if row['sleep_debt_3d'] > 5:
            risk += 0.15
        
        # HRV drop < -8: Significant autonomic nervous system stress
        # Indicates poor recovery state
        if row['hrv_drop'] < -8:
            risk += 0.15
        
        # High stress level (>=8/10): Psychological stress
        # Affects recovery and decision-making
        if row['stress_level'] >= 8:
            risk += 0.10
        
        # Previous injuries (>1): History is a risk factor
        if row['history_injury_count'] > 1:
            risk += 0.05
        
        # Cap risk between 0% and 95% (never 100% certain)
        return min(0.95, max(0.0, risk))

    # Generate injury labels based on calculated risk probability
    # Each row has a probability of injury, we sample from it
    df['injury_risk_probability'] = df.apply(calculate_injury_risk, axis=1)
    df['injury_tomorrow'] = df['injury_risk_probability'].apply(
        lambda p: 1 if np.random.rand() < p else 0
    )
    
    # ============================================================================
    # DATA CLEANUP
    # ============================================================================
    # Remove intermediate columns and handle missing values
    # Keep only features needed for model training
    final_df = df.dropna().drop([
        'athlete_id',           # Not a feature
        'date',                 # Not a feature
        'hrv_rolling_7d',       # Intermediate calculation (we have hrv_drop)
        'injury_risk_probability'  # This is the target calculation, not a feature
    ], axis=1)
    
    return final_df


def _write_quality_report(df: pd.DataFrame, output_dir: str) -> str:
    class_counts = df["injury_tomorrow"].value_counts().to_dict()
    injury_rate = float(df["injury_tomorrow"].mean())
    report = {
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "injury_rate": injury_rate,
        "class_counts": {str(k): int(v) for k, v in class_counts.items()},
        "acwr_ratio_range": [float(df["acwr_ratio"].min()), float(df["acwr_ratio"].max())],
        "sleep_debt_3d_range": [float(df["sleep_debt_3d"].min()), float(df["sleep_debt_3d"].max())],
        "hrv_drop_range": [float(df["hrv_drop"].min()), float(df["hrv_drop"].max())],
    }
    output_path = os.path.join(output_dir, "dataset_quality_report.json")
    import json

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic athlete injury dataset.")
    parser.add_argument("--num-athletes", type=int, default=NUM_ATHLETES)
    parser.add_argument("--days", type=int, default=DAYS_PER_ATHLETE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()

    df = generate_synthetic_data(
        num_athletes=args.num_athletes,
        days_per_athlete=args.days,
        seed=args.seed,
    )
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, "athlete_injury_data.csv")
    df.to_csv(output_path, index=False)
    report_path = _write_quality_report(df, script_dir)
    print(f"SUCCESS: Created {output_path}")
    print(f"QUALITY REPORT: {report_path}")