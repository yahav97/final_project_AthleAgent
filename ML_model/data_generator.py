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

import pandas as pd
import numpy as np

# ============================================================================
# CONFIGURATION
# ============================================================================

NUM_ATHLETES = 100          # Number of synthetic athletes
DAYS_PER_ATHLETE = 90       # Days of data per athlete (~3 months)
START_DATE = '2025-01-01'   # Starting date for data generation

# For validation set generation
VALIDATION_ATHLETES = 30    # Number of athletes for validation set
VALIDATION_DAYS = 60        # Days per athlete for validation

# ============================================================================
# DATA GENERATION FUNCTION
# ============================================================================

def generate_synthetic_data():
    all_data = []
    print(f"Generating data for {NUM_ATHLETES} athletes over {DAYS_PER_ATHLETE} days...")

    for athlete_id in range(1, NUM_ATHLETES + 1):
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
        dates = pd.date_range(start=START_DATE, periods=DAYS_PER_ATHLETE)
        
        for day in range(DAYS_PER_ATHLETE):
            # ============================================================
            # PHYSICAL LOAD METRICS
            # ============================================================
            # Daily training distance (km) - More realistic training patterns
            # Athletes have training cycles: some days high, some low, some rest
            day_in_week = day % 7
            if day_in_week == 0 or day_in_week == 6:  # Weekend - often rest or light
                daily_distance = np.random.gamma(shape=1.5, scale=2) if np.random.rand() > 0.3 else 0
            else:  # Weekday - more training
                daily_distance = np.random.gamma(shape=2.5, scale=3.5)
            if daily_distance < 0.5: daily_distance = 0  # Rest days
            
            # Workout intensity (minutes) - correlated with distance
            workout_intensity = int(daily_distance * np.random.randint(4, 7)) if daily_distance > 0 else 0
            
            # Average cadence (steps/min) - typical running cadence ~170
            avg_cadence = np.random.normal(170, 5) if daily_distance > 0 else 0
            
            # ============================================================
            # SLEEP AND RECOVERY METRICS
            # ============================================================
            # Sleep hours - normal distribution around 7 hours, bounded 3-10
            sleep_hours = max(3, min(10, np.random.normal(7, 1.5)))
            
            # HRV (Heart Rate Variability) - strongly affected by sleep, training load, and stress
            # More realistic correlation with other factors
            hrv_fluctuation = np.random.normal(0, 4)
            if sleep_hours < 5:  # Poor sleep reduces HRV significantly
                hrv_fluctuation -= 12
            elif sleep_hours < 6:
                hrv_fluctuation -= 6
            # High training load reduces HRV
            if daily_distance > 12:
                hrv_fluctuation -= 8
            elif daily_distance > 8:
                hrv_fluctuation -= 4
            hrv_score = int(base_hrv + hrv_fluctuation)
            hrv_score = max(20, min(100, hrv_score))  # Keep in reasonable range
            
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
            # Stress level (1-10 scale) - correlated with training load and sleep
            # Higher training load + poor sleep = higher stress
            base_stress = 3.0
            if daily_distance > 10:
                base_stress += 2.0
            if sleep_hours < 6:
                base_stress += 1.5
            if hrv_score < base_hrv - 10:
                base_stress += 1.0
            stress_level = max(1, min(10, int(np.random.normal(base_stress, 1.5))))
            
            # Muscle soreness (1-10 scale) - strongly correlated with training load
            base_soreness = 2.0
            if daily_distance > 12:
                base_soreness += 4.0
            elif daily_distance > 8:
                base_soreness += 2.5
            elif daily_distance > 5:
                base_soreness += 1.0
            # Poor recovery increases soreness
            if sleep_hours < 6:
                base_soreness += 1.0
            # HRV drop will be calculated later, but we can estimate from current HRV
            if hrv_score < base_hrv - 10:
                base_soreness += 0.5
            muscle_soreness = max(1, min(10, int(np.random.normal(base_soreness, 1.0))))

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
    # INJURY RISK CALCULATION (Optimized for Balanced Learning)
    # ============================================================================
    # Based on research-validated risk factors
    # Adjusted to create balanced dataset (25-30% injuries) for better model learning
    # Uses multiplicative/weighted approach - more aggressive to create more injuries
    def calculate_injury_risk(row):
        base_risk = 0.08  # Higher base risk (8%) to create more injuries for learning
        
        # Calculate risk multipliers (more aggressive to create balanced dataset)
        risk_multiplier = 1.0
        
        # ACWR > 1.2: High acute-to-chronic workload (Gabbett, 2016)
        # Lowered threshold significantly to catch more cases
        # Strongest predictor - multiplies risk by 3-5x
        if row['acwr_ratio'] > 1.5:
            risk_multiplier *= 5.0  # Very high ACWR
        elif row['acwr_ratio'] > 1.4:
            risk_multiplier *= 3.5  # High ACWR
        elif row['acwr_ratio'] > 1.3:
            risk_multiplier *= 2.5  # Moderate-high ACWR
        elif row['acwr_ratio'] > 1.2:  # Even lower threshold
            risk_multiplier *= 1.8  # Moderate ACWR
        
        # Sleep debt > 3 hours: Significant sleep deprivation
        # Lowered threshold significantly to catch more cases
        # Multiplies risk by 1.5-2.5x
        if row['sleep_debt_3d'] > 8:
            risk_multiplier *= 2.5  # Very high sleep debt
        elif row['sleep_debt_3d'] > 5:
            risk_multiplier *= 2.0  # High sleep debt
        elif row['sleep_debt_3d'] > 3:  # Lower threshold
            risk_multiplier *= 1.5  # Moderate sleep debt
        
        # HRV drop < -5: Significant autonomic nervous system stress
        # Lowered threshold significantly to catch more cases
        # Multiplies risk by 1.5-2.5x
        if row['hrv_drop'] < -12:
            risk_multiplier *= 2.5  # Very large HRV drop
        elif row['hrv_drop'] < -8:
            risk_multiplier *= 2.0  # Significant HRV drop
        elif row['hrv_drop'] < -5:  # Lower threshold
            risk_multiplier *= 1.5  # Moderate HRV drop
        
        # High stress level (>=6/10): Psychological stress
        # Lowered threshold significantly to catch more cases
        # Multiplies risk by 1.2-1.8x
        if row['stress_level'] >= 9:
            risk_multiplier *= 1.8  # Very high stress
        elif row['stress_level'] >= 8:
            risk_multiplier *= 1.5  # High stress
        elif row['stress_level'] >= 6:  # Lower threshold
            risk_multiplier *= 1.3  # Moderate-high stress
        
        # Previous injuries (>=1): History is a risk factor
        # Any injury history significantly increases risk
        # Adds base risk increase
        history_risk = 0.0
        if row['history_injury_count'] >= 3:
            history_risk = 0.12  # High history
        elif row['history_injury_count'] >= 2:
            risk_multiplier *= 1.3  # Medium history - also multiplies
            history_risk = 0.08
        elif row['history_injury_count'] >= 1:
            risk_multiplier *= 1.2  # Low history - also multiplies
            history_risk = 0.05
        
        # Additional factors that increase risk
        # High training load without proper recovery
        if row['daily_distance_km'] > 10 and row['sleep_hours'] < 6:
            risk_multiplier *= 1.4  # High load + poor sleep
        
        # Poor calorie balance (negative = not enough fuel)
        if row['calorie_balance'] < -500:
            risk_multiplier *= 1.3  # Significant calorie deficit
        
        # Calculate final risk: base * multiplier + history
        risk = (base_risk * risk_multiplier) + history_risk
        
        # Cap risk between 5% and 90% (allows more injuries for learning)
        return min(0.90, max(0.05, risk))

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

def generate_validation_data():
    """
    Generate a separate validation dataset with different athletes and time period.
    This ensures the model is tested on truly unseen data.
    """
    global NUM_ATHLETES, DAYS_PER_ATHLETE, START_DATE
    # Temporarily change settings for validation
    original_athletes = NUM_ATHLETES
    original_days = DAYS_PER_ATHLETE
    original_start = START_DATE
    
    NUM_ATHLETES = VALIDATION_ATHLETES
    DAYS_PER_ATHLETE = VALIDATION_DAYS
    START_DATE = '2025-04-01'  # Different time period
    
    validation_df = generate_synthetic_data()
    
    # Restore original settings
    NUM_ATHLETES = original_athletes
    DAYS_PER_ATHLETE = original_days
    START_DATE = original_start
    
    return validation_df

if __name__ == "__main__":
    import os
    df = generate_synthetic_data()
    # Save to ML_model directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, 'athlete_injury_data.csv')
    df.to_csv(output_path, index=False)
    print(f"SUCCESS: Created {output_path}")
    
    # Also generate validation set
    val_df = generate_validation_data()
    val_output_path = os.path.join(script_dir, 'athlete_injury_validation.csv')
    val_df.to_csv(val_output_path, index=False)
    print(f"SUCCESS: Created validation set {val_output_path}")