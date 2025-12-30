import pandas as pd
import numpy as np

# General settings
NUM_ATHLETES = 100
DAYS_PER_ATHLETE = 90
START_DATE = '2025-01-01'

def generate_synthetic_data():
    all_data = []
    print(f"Generating data for {NUM_ATHLETES} athletes over {DAYS_PER_ATHLETE} days...")

    for athlete_id in range(1, NUM_ATHLETES + 1):
        age = np.random.randint(18, 40)
        height = np.random.normal(1.75, 0.10)
        weight = np.random.normal(75, 10)
        bmi = round(weight / (height ** 2), 2)
        vo2_max = np.random.randint(40, 65)
        history_injury_count = np.random.choice([0, 1, 2, 3], p=[0.6, 0.2, 0.1, 0.1])
        base_hrv = np.random.randint(40, 90)
        base_resting_hr = np.random.randint(45, 65)
        dates = pd.date_range(start=START_DATE, periods=DAYS_PER_ATHLETE)
        
        for day in range(DAYS_PER_ATHLETE):
            daily_distance = np.random.gamma(shape=2, scale=3)
            if daily_distance < 1: daily_distance = 0
            
            workout_intensity = int(daily_distance * np.random.randint(4, 7)) if daily_distance > 0 else 0
            avg_cadence = np.random.normal(170, 5) if daily_distance > 0 else 0
            
            sleep_hours = max(3, min(10, np.random.normal(7, 1.5)))
            
            hrv_fluctuation = np.random.normal(0, 5)
            if sleep_hours < 5: hrv_fluctuation -= 10
            hrv_score = int(base_hrv + hrv_fluctuation)
            resting_hr = int(base_resting_hr + (np.random.normal(0, 2)))
            
            daily_calories = int(np.random.normal(2500, 300))
            active_burn = int(daily_distance * 60)
            bmr = int(10 * weight + 6.25 * (height*100) - 5 * age + 5)
            total_burned = bmr + active_burn
            
            stress_level = np.random.randint(1, 11)
            muscle_soreness = np.random.randint(1, 11)
            if daily_distance > 10: muscle_soreness += 2

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
    
    # Engineering calculations
    df['acute_load_7d'] = df.groupby('athlete_id')['daily_distance_km'].transform(lambda x: x.rolling(7).mean())
    df['chronic_load_21d'] = df.groupby('athlete_id')['daily_distance_km'].transform(lambda x: x.rolling(21).mean())
    df['acwr_ratio'] = df['acute_load_7d'] / df['chronic_load_21d'].replace(0, np.nan)
    df['acwr_ratio'] = df['acwr_ratio'].fillna(1.0)
    df['calorie_balance'] = df['daily_calories'] - df['total_calories_burned']
    df['sleep_debt_3d'] = df.groupby('athlete_id')['sleep_hours'].transform(lambda x: (8 - x).rolling(3).sum())
    df['hrv_rolling_7d'] = df.groupby('athlete_id')['hrv_score'].transform(lambda x: x.rolling(7).mean())
    df['hrv_drop'] = df['hrv_score'] - df['hrv_rolling_7d']

    # Injury risk calculation
    def calculate_injury_risk(row):
        risk = 0.05
        if row['acwr_ratio'] > 1.4: risk += 0.35
        if row['sleep_debt_3d'] > 5: risk += 0.15
        if row['hrv_drop'] < -8: risk += 0.15
        if row['stress_level'] >= 8: risk += 0.10
        if row['history_injury_count'] > 1: risk += 0.05
        return min(0.95, max(0.0, risk))

    df['injury_tomorrow'] = df.apply(calculate_injury_risk, axis=1).apply(lambda p: 1 if np.random.rand() < p else 0)
    
    # Clean up and save
    final_df = df.dropna().drop(['athlete_id', 'date', 'hrv_rolling_7d'], axis=1)
    return final_df

if __name__ == "__main__":
    import os
    df = generate_synthetic_data()
    # Save to ML_model directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, 'athlete_injury_data.csv')
    df.to_csv(output_path, index=False)
    print(f"SUCCESS: Created {output_path}")