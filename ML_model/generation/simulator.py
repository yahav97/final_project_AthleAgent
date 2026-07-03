"""Per-athlete day-by-day synthetic injury simulation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from feature_contract import workout_intensity_minutes
from generation.config import (
    ANNUAL_CYCLE_DAYS,
    DAYS_PER_ATHLETE,
    DEFAULT_SEED,
    NUM_ATHLETES,
    START_DATE,
)
from generation.postprocess import finalize_dataset
from policy_config import DEFAULT_SLEEP_TARGET_HOURS


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + np.exp(-x))


def _rolling_mean(values: list[float], window: int) -> float:
    tail = values[-window:] if len(values) >= window else values
    return float(np.mean(tail)) if tail else 0.0


def _acwr_baseline_from_distance_tail(distance_history_km: list[float], window: int = 7) -> float:
    tail = distance_history_km[-window:] if len(distance_history_km) >= window else distance_history_km
    if not tail:
        return 0.55
    weekly_mean = float(np.mean(tail))
    weekly_std = float(np.std(tail, ddof=1)) if len(tail) > 1 else 0.0
    return float(max(0.55, weekly_mean * 0.85 + weekly_std * 0.35 + 0.5))


def _bounded(value: float, low: float, high: float) -> float:
    return float(min(high, max(low, value)))


def compute_training_reference_features(
    distance_history_km: list[float],
    sleep_history_hours: list[float],
    hrv_history_scores: list[float],
) -> dict[str, float]:
    """Reference feature formulas — exposed for train/serve parity tests."""
    if not distance_history_km or not sleep_history_hours or not hrv_history_scores:
        raise ValueError("distance/sleep/hrv history lists must be non-empty")
    acute_load_7d = _rolling_mean(distance_history_km, 7)
    acwr_ratio = _bounded(
        acute_load_7d / _acwr_baseline_from_distance_tail(distance_history_km, window=7),
        0.35,
        2.8,
    )
    sleep_debt_3d = float(
        sum(max(0.0, DEFAULT_SLEEP_TARGET_HOURS - s) for s in sleep_history_hours[-3:])
    )
    hrv_drop = float(
        max(-15.0, min(15.0, hrv_history_scores[-1] - _rolling_mean(hrv_history_scores, 7)))
    )
    return {
        "acute_load_7d": acute_load_7d,
        "acwr_ratio": acwr_ratio,
        "sleep_debt_3d": sleep_debt_3d,
        "hrv_drop": hrv_drop,
    }


def _simulate_raw_rows(
    *,
    num_athletes: int,
    days_per_athlete: int,
    seed: int,
) -> list[dict]:
    rng = np.random.default_rng(seed)
    all_data: list[dict] = []
    print(
        f"Generating data for {num_athletes} athletes over {days_per_athlete} days "
        f"(seed={seed})..."
    )

    for athlete_id in range(1, num_athletes + 1):
        height = float(rng.normal(1.75, 0.10))
        weight = float(rng.normal(75, 10))
        bmi = round(weight / (height ** 2), 2)
        athlete_age = int(rng.integers(18, 41))
        career_injury_episodes = 0
        base_hrv = int(rng.integers(40, 90))
        base_resting_hr = int(rng.integers(45, 65))
        base_body_fat = float(rng.uniform(8.0, 25.0))
        base_vo2max = float(rng.uniform(35.0, 65.0))
        has_power_meter = bool(rng.random() < 0.30)
        base_power = float(rng.uniform(150.0, 400.0)) if has_power_meter else 0.0
        base_respiratory_rate = float(rng.uniform(12.0, 18.0))
        base_spo2 = float(rng.uniform(96.0, 99.0))
        base_speed_factor = float(rng.uniform(0.8, 1.3))
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
        season_phase = float(rng.uniform(0.0, 2.0 * np.pi))
        mesocycle_phase = float(rng.uniform(0.0, 2.0 * np.pi))
        distance_history: list[float] = []
        sleep_history: list[float] = []
        hrv_history: list[float] = []
        post_injury_cooldown = 0
        prev_injury_today = 0

        for day in range(days_per_athlete):
            injured_yesterday = int(prev_injury_today)
            weekly_cycle = np.sin((2 * np.pi * (day % 7)) / 7.0)
            annual_cycle = np.sin((2 * np.pi * day / ANNUAL_CYCLE_DAYS) + season_phase)
            mesocycle = np.sin((2 * np.pi * day / 28.0) + mesocycle_phase)
            microcycle_week = (day // 7) % 4
            microcycle_load = 1.08 if microcycle_week in (0, 1, 2) else 0.86
            recovery_boost = -0.25 if post_injury_cooldown > 0 else 0.0
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
            daily_distance = max(0.0, 0.55 * prior_load_km + 0.45 * target_km)
            if rng.random() < 0.12:
                daily_distance *= float(rng.uniform(0.0, 0.4))
            daily_distance = _bounded(daily_distance, 0.0, 22.0)
            prior_load_km = daily_distance

            active_calories_burned = int(
                _bounded(daily_distance * rng.uniform(55, 75), 0.0, 1800.0)
            )
            workout_intensity = workout_intensity_minutes(daily_distance, float(active_calories_burned))
            avg_cadence = _bounded(166.0 + rng.normal(0, 6) + daily_distance * 0.35, 145.0, 192.0)

            session_minutes = max(5.0, float(workout_intensity)) if daily_distance > 0.2 else 0.0
            avg_speed = _bounded(
                (daily_distance / (session_minutes / 60.0)) * base_speed_factor + rng.normal(0, 0.4),
                0.0, 20.0,
            ) if session_minutes > 0 else 0.0
            max_speed = _bounded(avg_speed * rng.uniform(1.15, 1.45), 0.0, 28.0) if avg_speed > 0 else 0.0

            elevation_gained = _bounded(
                daily_distance * rng.uniform(8, 55) + rng.normal(0, 15),
                0.0, 1200.0,
            ) if daily_distance > 0.3 else 0.0
            floors_climbed = max(0, int(round(elevation_gained / 3.0 + rng.normal(0, 1))))

            avg_power = 0.0
            if has_power_meter and daily_distance > 0.3:
                avg_power = _bounded(
                    base_power * (0.6 + 0.4 * daily_distance / 10.0) * microcycle_load + rng.normal(0, 15),
                    50.0, 600.0,
                )

            body_fat_pct = _bounded(
                base_body_fat + rng.normal(0, 0.3) + 0.1 * fatigue_state,
                5.0, 35.0,
            )
            vo2_max = _bounded(
                base_vo2max
                - 0.3 * fatigue_state
                + 0.2 * recovery_state
                + rng.normal(0, 0.5),
                25.0, 80.0,
            )

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

            respiratory_rate = _bounded(
                base_respiratory_rate
                + 0.3 * stress_signal
                + 0.15 * fatigue_state
                + 0.4 * external_shock
                + rng.normal(0, 0.8),
                8.0, 30.0,
            )
            spo2 = _bounded(
                base_spo2
                - 0.15 * daily_distance
                - 0.1 * max(0.0, stress_signal - 6.0)
                - 0.2 * max(0.0, fatigue_state - 1.0)
                - 0.3 * external_shock
                + rng.normal(0, 0.4),
                88.0, 100.0,
            )

            daily_calories = int(_bounded(rng.normal(2550 + 45 * training_phase, 260), 1600.0, 4200.0))
            nutrition_intake_calories = int(
                _bounded(float(daily_calories) + rng.normal(0.0, 180.0), 1200.0, 4500.0)
            )
            bmr = int(10 * weight + 6.25 * (height * 100) - 5 * athlete_age + 5)
            total_burned = int(_bounded(bmr + active_calories_burned, 1400.0, 5200.0))

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
            sensor_dropout = rng.random() < (0.012 + 0.008 * max(0.0, stress_signal - 7.0))
            if sensor_dropout:
                sleep_hours = _bounded(sleep_hours + rng.normal(0.0, 0.45), 4.5, 9.8)
                hrv_score = int(_bounded(hrv_score + rng.normal(0.0, 4.0), 30.0, 105.0))
                resting_hr = int(_bounded(resting_hr + rng.normal(0.0, 2.4), 40.0, 95.0))
                respiratory_rate = _bounded(respiratory_rate + rng.normal(0.0, 0.6), 8.0, 30.0)
                spo2 = _bounded(spo2 + rng.normal(0.0, 0.3), 88.0, 100.0)

            distance_history.append(float(daily_distance))
            sleep_history.append(float(sleep_hours))
            hrv_history.append(float(hrv_score))

            refs = compute_training_reference_features(distance_history, sleep_history, hrv_history)
            acwr_ratio = refs["acwr_ratio"]
            sleep_debt_3d = refs["sleep_debt_3d"]
            hrv_drop = refs["hrv_drop"]
            if len(sleep_history) >= 5:
                recent_sleep = sleep_history[-5:]
                sleep_trend_5d = float(np.polyfit(np.arange(5), recent_sleep, 1, full=False)[0])
            else:
                sleep_trend_5d = 0.0
            if len(distance_history) >= 5:
                recent_load = distance_history[-5:]
                load_trend_5d = float(np.polyfit(np.arange(5), recent_load, 1, full=False)[0])
            else:
                load_trend_5d = 0.0

            acwr_excess = max(0.0, acwr_ratio - 1.15)
            sleep_stress = max(0.0, sleep_debt_3d - 2.0)
            hrv_stress = max(0.0, -hrv_drop - 2.0)
            synergistic_overload = acwr_excess * sleep_stress
            synergistic_overload_exp = float(np.expm1(min(3.2, 1.4 * synergistic_overload)))
            recovery_protection = max(0.0, (sleep_hours - 7.4) + 0.08 * (hrv_score - base_hrv))
            calorie_surplus = float(nutrition_intake_calories - total_burned) / 1500.0
            spo2_stress = max(0.0, 95.0 - spo2)
            rr_elevation = max(0.0, respiratory_rate - base_respiratory_rate - 2.0)
            elevation_load = elevation_gained / 300.0
            speed_burst = max(0.0, max_speed - avg_speed * 1.3) / 5.0 if avg_speed > 1.0 else 0.0
            load_recovery_imbalance_day = acwr_ratio * sleep_debt_3d

            hazard_logit = (
                -4.25
                + 3.75 * acwr_excess
                + 0.40 * sleep_stress
                + 0.45 * hrv_stress
                + 0.12 * stress_level
                + 0.58 * synergistic_overload_exp
                + 0.72 * max(0.0, -sleep_trend_5d)
                + 0.50 * max(0.0, load_trend_5d)
                + (0.38 if post_injury_cooldown > 0 else 0.0)
                + 0.22 * injured_yesterday
                - 0.08 * (energy_level / 10.0)
                + 0.06 * calorie_surplus
                + 0.14 * external_shock
                + 0.04 * (athlete_age - 28.0) / 10.0
                + 0.16 * min(6, career_injury_episodes)
                - 0.45 * recovery_protection
                - 0.30 * resilience
                + 0.28 * spo2_stress
                + 0.20 * rr_elevation
                + 0.14 * elevation_load
                - 0.12 * max(0.0, (vo2_max - 45.0) / 20.0)
                + 0.09 * max(0.0, (body_fat_pct - 20.0) / 10.0)
                + 0.16 * speed_burst
                + 0.07 * max(0.0, muscle_soreness - 4.0)
                + 0.08 * (load_recovery_imbalance_day / 10.0)
            )
            injury_probability = _bounded(_sigmoid(hazard_logit), 0.004, 0.80)
            injury_today = int(rng.random() < injury_probability)

            if (
                injury_today == 1
                and acwr_ratio > 1.35
                and sleep_debt_3d > 3.5
                and (recovery_protection > 0.55 or resilience > 1.1)
                and rng.random() < 0.08
            ):
                injury_today = 0
            if (
                injury_today == 1
                and strong_athlete
                and acwr_ratio > 1.25
                and stress_level < 7
                and rng.random() < 0.10
            ):
                injury_today = 0
            if (
                injury_today == 0
                and acwr_ratio < 1.05
                and sleep_debt_3d < 1.5
                and stress_level < 5
                and rng.random() < 0.0004
            ):
                injury_today = 1
            if injury_today:
                post_injury_cooldown = int(rng.integers(4, 10))
                fatigue_state += 0.6
                recovery_state -= 0.45
                career_injury_episodes += 1
            else:
                post_injury_cooldown = max(0, post_injury_cooldown - 1)
                recovery_state += 0.06

            prev_injury_today = injury_today

            all_data.append(
                {
                    "athlete_id": athlete_id,
                    "date": dates[day],
                    "bmi": bmi,
                    "age": athlete_age,
                    "body_fat_pct": round(body_fat_pct, 1),
                    "vo2_max": round(vo2_max, 1),
                    "history_injury_count": career_injury_episodes,
                    "injured_yesterday": injured_yesterday,
                    "daily_distance_km": round(daily_distance, 2),
                    "workout_intensity_minutes": workout_intensity,
                    "avg_cadence": int(avg_cadence),
                    "elevation_gained_m": round(elevation_gained, 1),
                    "floors_climbed": floors_climbed,
                    "avg_speed": round(avg_speed, 2),
                    "max_speed": round(max_speed, 2),
                    "avg_power": round(avg_power, 1),
                    "active_calories_burned": active_calories_burned,
                    "sleep_hours": round(sleep_hours, 1),
                    "hrv_score": hrv_score,
                    "resting_hr": resting_hr,
                    "respiratory_rate": round(respiratory_rate, 1),
                    "spo2": round(spo2, 1),
                    "nutrition_intake_calories": nutrition_intake_calories,
                    "daily_calories": daily_calories,
                    "total_calories_burned": total_burned,
                    "stress_level": stress_level,
                    "muscle_soreness": min(10, muscle_soreness),
                    "energy_level": energy_level,
                    "injury_today": injury_today,
                }
            )

            fatigue_state = _bounded(
                0.72 * fatigue_state + 0.16 * (daily_distance / 10.0) + 0.07 * (stress_level / 10.0) + rng.normal(0, 0.2),
                -1.6,
                3.0,
            )
            recovery_state = _bounded(
                0.68 * recovery_state
                + 0.22 * (sleep_hours / DEFAULT_SLEEP_TARGET_HOURS)
                - 0.11 * (daily_distance / 10.0)
                + rng.normal(0, 0.17),
                -1.8,
                2.6,
            )

    return all_data


def generate_synthetic_data(
    num_athletes: int = NUM_ATHLETES,
    days_per_athlete: int = DAYS_PER_ATHLETE,
    seed: int = DEFAULT_SEED,
) -> pd.DataFrame:
    """Generate chronologically ordered synthetic athlete injury dataset.

    Args:
        num_athletes: Number of athletes to simulate.
        days_per_athlete: Number of sequential days per athlete.
        seed: RNG seed for reproducibility.

    Returns:
        pd.DataFrame: Training-ready dataframe including features and label.
    """
    raw_rows = _simulate_raw_rows(
        num_athletes=num_athletes,
        days_per_athlete=days_per_athlete,
        seed=seed,
    )
    return finalize_dataset(
        pd.DataFrame(raw_rows),
        num_athletes=num_athletes,
        days_per_athlete=days_per_athlete,
    )
