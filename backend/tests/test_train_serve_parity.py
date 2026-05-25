from pathlib import Path
import sys

from services.feature_engineering import compute_derived_features


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ML_model.data_generator import compute_training_reference_features  # noqa: E402


def test_training_and_serving_derived_features_parity_within_tolerance():
    # Simulated history context for a plausible athlete training week.
    distance_history = [5.0, 6.5, 8.0, 0.0, 9.0, 11.0, 7.0]
    sleep_history = [7.6, 7.2, 6.8, 8.1, 6.3, 6.1, 7.0]
    hrv_history = [68, 66, 64, 70, 61, 59, 62]

    training_ref = compute_training_reference_features(
        distance_history_km=distance_history,
        sleep_history_hours=sleep_history,
        hrv_history_scores=hrv_history,
    )

    serving_out = compute_derived_features(
        {
            "daily_distance_km": distance_history[-1],
            "_active_calories": distance_history[-1] * 65.0,
            "sleep_hours": sleep_history[-1],
            "hrv_score": hrv_history[-1],
            "resting_hr": 55.0,
        }
    )

    # Tolerances are intentionally loose because serving is currently a proxy path.
    assert abs(training_ref["acwr_ratio"] - serving_out["acwr_ratio"]) <= 0.45
    assert abs(training_ref["sleep_debt_3d"] - serving_out["sleep_debt_3d"]) <= 3.6
    assert abs(training_ref["hrv_drop"] - serving_out["hrv_drop"]) <= 7.0


def test_serving_proxy_direction_matches_training_signal_trends():
    # Low recovery state
    low_recovery_training = compute_training_reference_features(
        distance_history_km=[9.5, 10.0, 11.2, 8.8, 10.5, 12.0, 12.8],
        sleep_history_hours=[6.2, 6.1, 5.9, 6.0, 5.8, 5.7, 5.9],
        hrv_history_scores=[57, 56, 54, 55, 53, 52, 51],
    )
    low_recovery_serving = compute_derived_features(
        {
            "daily_distance_km": 12.8,
            "_active_calories": 820.0,
            "sleep_hours": 5.9,
            "hrv_score": 51.0,
            "resting_hr": 60.0,
        }
    )

    # Better recovery state
    high_recovery_training = compute_training_reference_features(
        distance_history_km=[4.0, 5.2, 4.8, 0.0, 5.5, 4.7, 4.4],
        sleep_history_hours=[8.1, 7.8, 8.2, 8.4, 7.9, 8.0, 8.2],
        hrv_history_scores=[70, 71, 72, 73, 71, 72, 73],
    )
    high_recovery_serving = compute_derived_features(
        {
            "daily_distance_km": 4.4,
            "_active_calories": 280.0,
            "sleep_hours": 8.2,
            "hrv_score": 73.0,
            "resting_hr": 49.0,
        }
    )

    # Even with approximation, ordering should be consistent.
    assert low_recovery_training["sleep_debt_3d"] > high_recovery_training["sleep_debt_3d"]
    assert low_recovery_serving["sleep_debt_3d"] > high_recovery_serving["sleep_debt_3d"]
    assert low_recovery_training["acwr_ratio"] >= high_recovery_training["acwr_ratio"]
    assert low_recovery_serving["acwr_ratio"] >= high_recovery_serving["acwr_ratio"]
