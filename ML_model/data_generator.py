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
- Calorie surplus relative to burn: additional load signal

Author: AthleAgent Project
"""

import argparse
import json
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

def _sigmoid(x: float) -> float:
    """Compute logistic sigmoid for hazard to probability conversion."""
    return 1.0 / (1.0 + np.exp(-x))


def _rolling_mean(values: list[float], window: int) -> float:
    """Compute rolling mean over tail window, fallback to full list."""
    tail = values[-window:] if len(values) >= window else values
    return float(np.mean(tail)) if tail else 0.0


def _bounded(value: float, low: float, high: float) -> float:
    """Clip scalar into closed interval [low, high]."""
    return float(min(high, max(low, value)))


def compute_training_reference_features(
    distance_history_km: list[float],
    sleep_history_hours: list[float],
    hrv_history_scores: list[float],
) -> dict[str, float]:
    """
    Reference feature formulas used by training (rolling windows from history).
    Exposed for train/serve parity tests.
    """
    if not distance_history_km or not sleep_history_hours or not hrv_history_scores:
        raise ValueError("distance/sleep/hrv history lists must be non-empty")

    acute_load_7d = _rolling_mean(distance_history_km, 7)
    chronic_load_21d = max(0.1, _rolling_mean(distance_history_km, 21))
    acwr_ratio = _bounded(acute_load_7d / chronic_load_21d, 0.35, 2.8)
    sleep_debt_3d = float(sum(max(0.0, 8.0 - s) for s in sleep_history_hours[-3:]))
    hrv_drop = float(hrv_history_scores[-1] - _rolling_mean(hrv_history_scores, 7))
    return {
        "acute_load_7d": acute_load_7d,
        "chronic_load_21d": chronic_load_21d,
        "acwr_ratio": acwr_ratio,
        "sleep_debt_3d": sleep_debt_3d,
        "hrv_drop": hrv_drop,
    }


def generate_synthetic_data(
    num_athletes: int = NUM_ATHLETES,
    days_per_athlete: int = DAYS_PER_ATHLETE,
    seed: int = DEFAULT_SEED,
):
    """Generate chronologically ordered synthetic athlete injury dataset.

    Args:
        num_athletes: Number of athletes to simulate.
        days_per_athlete: Number of sequential days per athlete.
        seed: RNG seed for reproducibility.

    Returns:
        pd.DataFrame: Training-ready dataframe including features and label.
    """
    rng = np.random.default_rng(seed)
    all_data = []
    print(
        f"Generating data for {num_athletes} athletes over {days_per_athlete} days "
        f"(seed={seed})..."
    )

    for athlete_id in range(1, num_athletes + 1):
        # Generate athlete baseline characteristics (constant per athlete)
        height = float(rng.normal(1.75, 0.10))  # Average height ~175cm
        weight = float(rng.normal(75, 10))      # Average weight ~75kg
        bmi = round(weight / (height ** 2), 2)
        athlete_age = int(rng.integers(18, 41))
        career_injury_episodes = 0
        base_hrv = int(rng.integers(40, 90))  # Baseline HRV (ms)
        base_resting_hr = int(rng.integers(45, 65))  # Baseline resting HR (bpm)
        dates = pd.date_range(start=START_DATE, periods=days_per_athlete)

        training_phase = float(rng.uniform(0.8, 1.35))
        resilience = float(rng.uniform(0.75, 1.2))
        strong_athlete = bool(rng.random() < 0.18)
        if strong_athlete:
            resilience = float(min(1.35, resilience + rng.uniform(0.12, 0.22)))
            training_phase = float(min(1.45, training_phase + rng.uniform(0.08, 0.16)))
        fatigue_state = float(rng.normal(0.0, 0.6))
        recovery_state = float(rng.normal(0.0, 0.5))
        prior_load_km = float(max(0.0, rng.normal(6.0, 2.0)))
        # Athlete-specific periodicity for yearly + mesocycle behavior.
        season_phase = float(rng.uniform(0.0, 2.0 * np.pi))
        mesocycle_phase = float(rng.uniform(0.0, 2.0 * np.pi))
        distance_history: list[float] = []
        sleep_history: list[float] = []
        hrv_history: list[float] = []
        post_injury_cooldown = 0
        prev_injury_tomorrow = 0

        for day in range(days_per_athlete):
            injured_yesterday = int(prev_injury_tomorrow)
            weekly_cycle = np.sin((2 * np.pi * (day % 7)) / 7.0)
            annual_cycle = np.sin((2 * np.pi * day / 365.0) + season_phase)
            mesocycle = np.sin((2 * np.pi * day / 28.0) + mesocycle_phase)
            # 3 build weeks + 1 deload week pattern.
            microcycle_week = (day // 7) % 4
            microcycle_load = 1.08 if microcycle_week in (0, 1, 2) else 0.86
            recovery_boost = -0.25 if post_injury_cooldown > 0 else 0.0
            # Rare external stressors (travel/illness/life stress) with short persistence.
            external_shock = 0.0
            if rng.random() < 0.015:
                external_shock = float(rng.uniform(0.8, 1.8))
            load_noise = float(rng.normal(0.0, 1.2))
            target_km = (
                4.8 * training_phase
                + 1.8 * weekly_cycle
                + 0.9 * annual_cycle
                + 0.7 * mesocycle
                + 1.4 * fatigue_state
                - 1.1 * recovery_state
                + recovery_boost
                + load_noise
            )
            target_km *= microcycle_load
            # AR(1) smoothing for realistic day-to-day continuity in load.
            daily_distance = max(0.0, 0.55 * prior_load_km + 0.45 * target_km)
            if rng.random() < 0.12:
                daily_distance *= float(rng.uniform(0.0, 0.4))  # rest/low-load day
            daily_distance = _bounded(daily_distance, 0.0, 22.0)
            prior_load_km = daily_distance

            workout_intensity = int(
                _bounded(daily_distance * rng.uniform(4.2, 6.1) * microcycle_load, 0.0, 180.0)
            )
            avg_cadence = _bounded(166.0 + rng.normal(0, 6) + daily_distance * 0.35, 145.0, 192.0)

            stress_signal = _bounded(
                4.6
                + 1.0 * fatigue_state
                - 1.0 * recovery_state
                + 0.55 * external_shock
                + rng.normal(0.0, 1.1),
                1.0,
                10.0,
            )
            sleep_hours = _bounded(
                8.35
                - 0.12 * stress_signal
                - 0.08 * daily_distance
                - 0.25 * external_shock
                + rng.normal(0, 0.6),
                4.5,
                9.8,
            )
            hrv_score = int(
                _bounded(
                    base_hrv
                    - 1.6 * stress_signal
                    - 0.65 * fatigue_state
                    + 1.1 * recovery_state
                    - 1.4 * external_shock
                    + rng.normal(0, 3.8),
                    30.0,
                    105.0,
                )
            )
            resting_hr = int(
                _bounded(
                    base_resting_hr
                    + 0.9 * stress_signal
                    + 0.3 * daily_distance
                    + 1.2 * external_shock
                    + rng.normal(0, 1.8),
                    40.0,
                    95.0,
                )
            )

            daily_calories = int(_bounded(rng.normal(2550 + 45 * training_phase, 260), 1600.0, 4200.0))
            nutrition_intake_calories = int(
                _bounded(float(daily_calories) + rng.normal(0.0, 180.0), 1200.0, 4500.0)
            )
            active_burn = int(_bounded(daily_distance * rng.uniform(55, 75), 0.0, 1800.0))
            # Mifflin–St Jeor (male); age is also a model feature in production.
            bmr = int(10 * weight + 6.25 * (height * 100) - 5 * athlete_age + 5)
            total_burned = int(_bounded(bmr + active_burn, 1400.0, 5200.0))

            muscle_soreness = int(
                round(
                    _bounded(
                        2.3 + 0.28 * daily_distance + 0.38 * stress_signal + 0.6 * fatigue_state + rng.normal(0, 1.1),
                        1.0,
                        10.0,
                    )
                )
            )
            stress_level = int(round(stress_signal))
            energy_level = int(
                round(
                    _bounded(
                        10.0
                        - 0.52 * float(stress_level)
                        + 0.28 * recovery_state
                        - 0.35 * external_shock
                        + rng.normal(0.0, 1.25),
                        1.0,
                        10.0,
                    )
                )
            )
            # Structured sensor dropouts: more likely under high stress/low recovery states.
            sensor_dropout = rng.random() < (0.018 + 0.01 * max(0.0, stress_signal - 7.0))
            if sensor_dropout:
                sleep_hours = _bounded(sleep_hours + rng.normal(0.0, 0.45), 4.5, 9.8)
                hrv_score = int(_bounded(hrv_score + rng.normal(0.0, 4.0), 30.0, 105.0))
                resting_hr = int(_bounded(resting_hr + rng.normal(0.0, 2.4), 40.0, 95.0))

            distance_history.append(float(daily_distance))
            sleep_history.append(float(sleep_hours))
            hrv_history.append(float(hrv_score))

            refs = compute_training_reference_features(distance_history, sleep_history, hrv_history)
            acute_load_7d = refs["acute_load_7d"]
            chronic_load_21d = refs["chronic_load_21d"]
            acwr_ratio = refs["acwr_ratio"]
            sleep_debt_3d = refs["sleep_debt_3d"]
            hrv_drop = refs["hrv_drop"]
            if len(sleep_history) >= 5:
                recent_sleep = sleep_history[-5:]
                sleep_trend_5d = float(np.polyfit(np.arange(5), recent_sleep, 1)[0])
            else:
                sleep_trend_5d = 0.0
            if len(distance_history) >= 5:
                recent_load = distance_history[-5:]
                load_trend_5d = float(np.polyfit(np.arange(5), recent_load, 1)[0])
            else:
                load_trend_5d = 0.0

            # Hazard-based event model with episode persistence and cooldown.
            acwr_excess = max(0.0, acwr_ratio - 1.15)
            sleep_stress = max(0.0, sleep_debt_3d - 2.0)
            hrv_stress = max(0.0, -hrv_drop - 2.0)
            synergistic_overload = acwr_excess * sleep_stress
            synergistic_overload_exp = float(np.expm1(min(3.2, 1.15 * synergistic_overload)))
            recovery_protection = max(0.0, (sleep_hours - 7.4) + 0.06 * (hrv_score - base_hrv))
            calorie_surplus = float(nutrition_intake_calories - total_burned) / 1500.0

            hazard_logit = (
                -2.55
                + 2.00 * acwr_excess
                + 0.10 * sleep_stress
                + 0.13 * hrv_stress
                + 0.10 * stress_level
                + 0.16 * synergistic_overload_exp
                + 0.58 * max(0.0, -sleep_trend_5d)
                + 0.34 * max(0.0, load_trend_5d)
                + (0.35 if post_injury_cooldown > 0 else 0.0)
                + 0.18 * injured_yesterday
                - 0.08 * (energy_level / 10.0)
                + 0.07 * calorie_surplus
                + 0.12 * external_shock
                + 0.02 * (athlete_age - 28.0) / 10.0
                + 0.07 * min(6, career_injury_episodes)
                - 0.30 * recovery_protection
                - 0.22 * resilience
            )
            injury_probability = _bounded(_sigmoid(hazard_logit), 0.01, 0.92)
            injury_tomorrow = int(rng.random() < injury_probability)

            # Hard negatives: occasionally keep athletes healthy despite high apparent risk.
            if (
                injury_tomorrow == 1
                and acwr_ratio > 1.35
                and sleep_debt_3d > 3.5
                and (recovery_protection > 0.45 or resilience > 1.05)
                and rng.random() < 0.33
            ):
                injury_tomorrow = 0
            if (
                injury_tomorrow == 1
                and strong_athlete
                and acwr_ratio > 1.25
                and stress_level < 8
                and rng.random() < 0.38
            ):
                injury_tomorrow = 0

            # Rare unexplained injuries: preserve label noise and realism.
            if (
                injury_tomorrow == 0
                and acwr_ratio < 1.05
                and sleep_debt_3d < 1.5
                and stress_level < 5
                and rng.random() < 0.002
            ):
                injury_tomorrow = 1
            if injury_tomorrow:
                post_injury_cooldown = int(rng.integers(4, 10))
                fatigue_state += 0.6
                recovery_state -= 0.45
                career_injury_episodes += 1
            else:
                post_injury_cooldown = max(0, post_injury_cooldown - 1)
                recovery_state += 0.06

            prev_injury_tomorrow = injury_tomorrow

            row = {
                'athlete_id': athlete_id,
                'date': dates[day],
                'bmi': bmi,
                'age': athlete_age,
                'history_injury_count': career_injury_episodes,
                'injured_yesterday': injured_yesterday,
                'daily_distance_km': round(daily_distance, 2),
                'workout_intensity_minutes': workout_intensity, 'avg_cadence': int(avg_cadence),
                'sleep_hours': round(sleep_hours, 1), 'hrv_score': hrv_score, 'resting_hr': resting_hr,
                'nutrition_intake_calories': nutrition_intake_calories,
                'daily_calories': daily_calories, 'total_calories_burned': total_burned,
                'stress_level': stress_level, 'muscle_soreness': min(10, muscle_soreness),
                'energy_level': energy_level,
                'injury_tomorrow': injury_tomorrow,
            }
            all_data.append(row)

            fatigue_state = _bounded(
                0.72 * fatigue_state + 0.16 * (daily_distance / 10.0) + 0.07 * (stress_level / 10.0) + rng.normal(0, 0.2),
                -1.6,
                3.0,
            )
            recovery_state = _bounded(
                0.68 * recovery_state + 0.22 * (sleep_hours / 8.0) - 0.11 * (daily_distance / 10.0) + rng.normal(0, 0.17),
                -1.8,
                2.6,
            )

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
    df['acwr_ratio'] = df['acwr_ratio'].fillna(1.0).clip(0.35, 2.8)  # Keep consistent with serving bounds
    
    # Energy balance (calories in - calories out)
    df['calorie_balance'] = df['daily_calories'] - df['total_calories_burned']
    
    # Sleep debt - cumulative sleep deficit over 3 days (assuming 8h ideal)
    df['sleep_debt_3d'] = df.groupby('athlete_id')['sleep_hours'].transform(
        lambda x: (8 - x).clip(lower=0).rolling(3).sum()
    )
    
    # HRV rolling average (7-day baseline)
    df['hrv_rolling_7d'] = df.groupby('athlete_id')['hrv_score'].transform(
        lambda x: x.rolling(7).mean()
    )
    # HRV drop - negative values indicate stress/recovery issues
    df['hrv_drop'] = (df['hrv_score'] - df['hrv_rolling_7d']).clip(-15.0, 15.0)

    # ============================================================================
    # DATA CLEANUP
    # ============================================================================
    # Remove intermediate columns and handle missing values
    # Keep only features needed for model training
    final_df = df.dropna().drop(
        [
            'hrv_rolling_7d',  # Intermediate calculation (we have hrv_drop)
        ],
        axis=1,
    )
    final_df = final_df.sort_values(["athlete_id", "date"]).reset_index(drop=True)
    
    return final_df


def _write_quality_report(df: pd.DataFrame, output_dir: str) -> str:
    """Write dataset quality diagnostics JSON and return path."""
    class_counts = df["injury_tomorrow"].value_counts().to_dict()
    injury_rate = float(df["injury_tomorrow"].mean())
    corr = df[["daily_distance_km", "sleep_hours", "stress_level", "muscle_soreness", "acwr_ratio", "hrv_drop"]].corr()
    report = {
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "injury_rate": injury_rate,
        "class_counts": {str(k): int(v) for k, v in class_counts.items()},
        "acwr_ratio_range": [float(df["acwr_ratio"].min()), float(df["acwr_ratio"].max())],
        "sleep_debt_3d_range": [float(df["sleep_debt_3d"].min()), float(df["sleep_debt_3d"].max())],
        "hrv_drop_range": [float(df["hrv_drop"].min()), float(df["hrv_drop"].max())],
        "high_risk_condition_rates": {
            "acwr_gt_1_4": float((df["acwr_ratio"] > 1.4).mean()),
            "sleep_debt_gt_5": float((df["sleep_debt_3d"] > 5.0).mean()),
            "hrv_drop_lt_minus8": float((df["hrv_drop"] < -8.0).mean()),
            "stress_ge_8": float((df["stress_level"] >= 8).mean()),
        },
        "feature_correlations": {
            "distance_sleep": float(corr.loc["daily_distance_km", "sleep_hours"]),
            "distance_soreness": float(corr.loc["daily_distance_km", "muscle_soreness"]),
            "stress_sleep": float(corr.loc["stress_level", "sleep_hours"]),
            "stress_hrvdrop": float(corr.loc["stress_level", "hrv_drop"]),
        },
    }
    output_path = os.path.join(output_dir, "dataset_quality_report.json")

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