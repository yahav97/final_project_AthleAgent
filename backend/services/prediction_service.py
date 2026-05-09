"""Orchestration of preprocessing, features, and model.predict_proba."""

from __future__ import annotations

from typing import Any

from ml.model_loader import get_model, get_model_gate_reason
from schemas.inference import InjuryPredictionRequest
from services.history_service import (
    fetch_daily_firestore_snapshot,
    get_history_window_context,
    save_daily_prediction_result,
)
from services.model_features import DEFAULT_FEATURE_VALUES
from services.preprocessing import (
    calculate_data_quality_score,
    injury_request_to_model_dataframe,
    validate_feature_vector_for_model,
)
from utils.logging import logger


def _recommendation(probability: float, acwr: float) -> str:
    if probability >= 0.6:
        return "Reduce training load today; prioritize sleep and recovery."
    if probability >= 0.35 or acwr >= 1.35:
        return "Moderate risk: consider lighter session and monitor soreness and sleep."
    if acwr >= 1.2:
        return "ACWR elevated: keep volume stable and avoid sharp spikes this week."
    return "Maintain current load; continue monitoring sleep and subjective readiness."


def _apply_history_confidence_fallback(df, payload: InjuryPredictionRequest) -> tuple[Any, str]:
    """
    Enrich row with historical rolling features and return confidence label.

    - high/medium confidence: use computed rolling features from Firestore.
    - low confidence (new athlete, <7 days): prefer stable profile averages for rolling
      fields to avoid noisy short-window artifacts.
    """
    confidence = "low"
    if not (payload.userId and payload.date):
        return df, confidence

    context = get_history_window_context(
        payload.userId,
        payload.date,
        lookback_days=7,
        include_target_day=False,
    )
    confidence = str(context.get("confidence") or "low")
    features = context.get("features") or {}

    if confidence in ("high", "medium") and features:
        for col, value in features.items():
            if col in df.columns:
                df.at[df.index[0], col] = float(value)
        return df, confidence

    # New/insufficient history: use conservative profile averages for rolling fields.
    for col in (
        "acute_load_7d",
        "chronic_load_21d",
        "acwr_ratio",
        "acwr_ratio_ma7",
        "acwr_ratio_std21",
        "sleep_hours_ma7",
        "sleep_hours_std21",
        "sleep_debt_3d",
        "hrv_drop",
    ):
        if col in df.columns:
            df.at[df.index[0], col] = float(DEFAULT_FEATURE_VALUES[col])
    return df, confidence


def _backfill_today_row_from_recent_history(df, payload: InjuryPredictionRequest) -> tuple[Any, dict[str, bool]]:
    """
    Backfill missing current-day load/recovery anchors from the latest available
    historical snapshot (yesterday/recent week), while preserving today's survey fields.
    """
    fallback_flags = {"load": False, "recovery": False}
    if not (payload.userId and payload.date):
        return df, fallback_flags

    context = get_history_window_context(
        payload.userId,
        payload.date,
        lookback_days=7,
        include_target_day=False,
    )
    recent = context.get("recent_row") or {}
    if not recent:
        return df, fallback_flags

    # Load anchors
    distance_m = float(recent.get("distanceMeters") or 0.0)
    steps = float(recent.get("steps") or 0.0)
    if distance_m > 0:
        distance_km = distance_m / 1000.0
    elif steps > 0:
        distance_km = steps * 0.0008
    else:
        distance_km = 0.0

    active_cal = float(recent.get("activeCalories") or 0.0)
    workout_intensity = max(0.0, min(240.0, distance_km * 5.5 + active_cal / 40.0))
    if distance_km > 0 and "daily_distance_km" in df.columns and float(df.at[df.index[0], "daily_distance_km"]) <= 0.0:
        df.at[df.index[0], "daily_distance_km"] = float(distance_km)
        fallback_flags["load"] = True
    if workout_intensity > 0 and "workout_intensity_minutes" in df.columns and float(df.at[df.index[0], "workout_intensity_minutes"]) <= 0.0:
        df.at[df.index[0], "workout_intensity_minutes"] = float(workout_intensity)
        fallback_flags["load"] = True

    # Recovery anchors (do not override today's stress/soreness from survey)
    sleep_minutes = float(recent.get("sleepMinutes") or 0.0)
    sleep_hours = sleep_minutes / 60.0 if sleep_minutes > 0 else 0.0
    hr_min = float(recent.get("heartRateMin") or 0.0)
    hr_avg = float(recent.get("heartRateAvg") or 0.0)
    resting_hr = hr_min if hr_min > 0 else hr_avg
    if sleep_hours > 0 and "sleep_hours" in df.columns and float(df.at[df.index[0], "sleep_hours"]) <= 0.0:
        df.at[df.index[0], "sleep_hours"] = float(max(3.0, min(12.0, sleep_hours)))
        fallback_flags["recovery"] = True
    if resting_hr > 0 and "resting_hr" in df.columns and float(df.at[df.index[0], "resting_hr"]) <= 0.0:
        clipped_resting = float(max(38.0, min(95.0, resting_hr)))
        df.at[df.index[0], "resting_hr"] = clipped_resting
        if "hrv_score" in df.columns and float(df.at[df.index[0], "hrv_score"]) <= 0.0:
            df.at[df.index[0], "hrv_score"] = float(max(30.0, min(100.0, 110.0 - clipped_resting * 0.65)))
        fallback_flags["recovery"] = True

    return df, fallback_flags


def _append_confidence_note(recommendation: str, confidence: str) -> str:
    if confidence == "high":
        return recommendation + " Confidence: high (7-day history available)."
    if confidence == "medium":
        return recommendation + " Confidence: medium (partial history available)."
    return recommendation + " Confidence: low (insufficient history; using profile/default baselines)."


def _history_score_from_confidence(confidence: str) -> float:
    if confidence == "high":
        return 0.95
    if confidence == "medium":
        return 0.7
    return 0.45


def _combined_confidence(history_confidence: str, quality_score: float) -> str:
    score = 0.6 * _history_score_from_confidence(history_confidence) + 0.4 * quality_score
    if score >= 0.78:
        return "high"
    if score >= 0.52:
        return "medium"
    return "low"


def _confidence_bucket(probability: float, high_cutoff: float, medium_cutoff: float) -> str:
    if probability >= high_cutoff + 0.12:
        return "High"
    if probability >= high_cutoff:
        return "Medium"
    if probability >= medium_cutoff:
        return "Medium"
    return "Low"


def _quality_status(quality_score: float) -> str:
    if quality_score >= 0.9:
        return "Excellent"
    if quality_score >= 0.7:
        return "Good"
    if quality_score >= 0.45:
        return "Fair"
    return "Poor"


def _count_defaulted_critical_features(df) -> int:
    critical = (
        "acute_load_7d",
        "chronic_load_21d",
        "acwr_ratio",
        "acwr_ratio_ma7",
        "acwr_ratio_std21",
        "sleep_hours_ma7",
        "sleep_hours_std21",
        "sleep_debt_3d",
        "hrv_drop",
    )
    count = 0
    for col in critical:
        if col not in df.columns:
            continue
        observed = float(df[col].iloc[0])
        default = float(DEFAULT_FEATURE_VALUES[col])
        if abs(observed - default) < 1e-9:
            count += 1
    return count


def _resolve_model_bundle(
    loaded_model: Any,
) -> tuple[Any | None, list[str] | None, float | None, float | None, str, str]:
    """
    Enforce a single model contract for serving.

    Required bundle format (saved by ML_model/train_model.py):
      {
        "estimator": <model>,
        "feature_columns": [...],
        "threshold": <float>,
        "winner": <str>
      }
    """
    if loaded_model is None:
        return None, None, None, None, "fallback_demo", "model_not_loaded"
    if not isinstance(loaded_model, dict):
        return None, None, None, None, "fallback_demo", "unsupported_model_format"

    estimator = loaded_model.get("estimator")
    feature_columns = loaded_model.get("feature_columns")
    threshold_raw = loaded_model.get("threshold")
    medium_threshold_raw = loaded_model.get("medium_threshold")
    winner = str(loaded_model.get("winner") or "live_model")

    if estimator is None:
        return None, None, None, None, "fallback_demo", "missing_estimator"
    if not isinstance(feature_columns, list) or not feature_columns:
        return None, None, None, None, "fallback_demo", "missing_feature_columns"
    try:
        threshold = float(threshold_raw)
    except (TypeError, ValueError):
        return None, None, None, None, "fallback_demo", "invalid_threshold"
    try:
        medium_threshold = (
            float(medium_threshold_raw)
            if medium_threshold_raw is not None
            else max(0.15, threshold * 0.6)
        )
    except (TypeError, ValueError):
        return None, None, None, None, "fallback_demo", "invalid_medium_threshold"

    return estimator, [str(c) for c in feature_columns], threshold, medium_threshold, winner, "none"


def predict_injury_risk(payload: InjuryPredictionRequest) -> dict[str, Any]:
    """
    Run preprocessing → feature row → sklearn ``predict_proba`` (injury positive class).

    If ``injury_model.pkl`` is not present on the server, returns a conservative demo
    response so local development and CI still behave predictably.
    """
    df = injury_request_to_model_dataframe(payload)
    df, fallback_used = _backfill_today_row_from_recent_history(df, payload)
    df, history_confidence = _apply_history_confidence_fallback(df, payload)
    quality = calculate_data_quality_score(payload)
    quality_score = float(quality["score"])
    quality_status = _quality_status(quality_score)
    logger.info(
        "predict_data_quality userId=%s date=%s quality=%.3f sensitive_missing_fields=%s hard_missing=%s",
        payload.userId,
        payload.date,
        quality_score,
        quality.get("sensitive_missing", []),
        quality.get("hard_missing", []),
    )
    final_confidence = _combined_confidence(history_confidence, quality_score)
    defaulted_critical_count = _count_defaulted_critical_features(df)
    logger.info(
        "predict_confidence_summary userId=%s confidence=%s defaulted_critical=%d",
        payload.userId,
        final_confidence,
        defaulted_critical_count,
    )

    hard_missing = set(quality.get("hard_missing", []))
    only_signal_blockers = hard_missing.issubset({"load_signal", "recovery_signal"})
    if bool(quality["has_hard_blocker"]) and only_signal_blockers and (fallback_used["load"] or fallback_used["recovery"]):
        quality_score = max(quality_score, 0.45)
        logger.info(
            "predict_quality_relaxed_from_history userId=%s load_fallback=%s recovery_fallback=%s",
            payload.userId,
            fallback_used["load"],
            fallback_used["recovery"],
        )

    if bool(quality["has_hard_blocker"]) and not (
        only_signal_blockers and (fallback_used["load"] or fallback_used["recovery"])
    ):
        logger.warning(
            "predict_blocked userId=%s reason=insufficient_input_quality confidence=%s",
            payload.userId,
            final_confidence,
        )
        raise ValueError("insufficient_input_quality")
    if quality_score < 0.35:
        logger.warning(
            "predict_blocked userId=%s reason=insufficient_input_quality confidence=%s",
            payload.userId,
            final_confidence,
        )
        raise ValueError("insufficient_input_quality")
    acwr = float(df["acwr_ratio"].iloc[0])

    loaded_model = get_model()
    (
        model,
        bundle_feature_columns,
        model_threshold,
        medium_threshold,
        model_version,
        model_status,
    ) = _resolve_model_bundle(loaded_model)
    if model is None:
        gate_reason = get_model_gate_reason()
        blocked_reason = model_status if model_status != "model_not_loaded" else gate_reason
        logger.warning(
            "predict_blocked userId=%s reason=%s confidence=%s",
            payload.userId,
            blocked_reason,
            final_confidence,
        )
        raise RuntimeError(f"model_not_live:{blocked_reason}")

    # Saved estimators may have been trained after feature selection (subset of MODEL_FEATURE_COLUMNS).
    model_contract = {"estimator": model, "feature_columns": bundle_feature_columns}
    X = validate_feature_vector_for_model(df, model_contract)

    proba = float(model.predict_proba(X)[0, 1])
    # Single source of truth: operating threshold comes from the saved model bundle.
    high_cutoff = float(model_threshold)
    medium_cutoff = min(float(medium_threshold), high_cutoff)
    risk_level = "High" if proba >= high_cutoff else "Medium" if proba >= medium_cutoff else "Low"
    confidence_bucket = _confidence_bucket(proba, high_cutoff, medium_cutoff)

    return {
        "risk_level": risk_level,
        "risk_score": round(proba, 4),
        "recommendation": _append_confidence_note(_recommendation(proba, acwr), final_confidence),
        "data_quality_score": round(quality_score, 4),
        "data_quality_status": quality_status,
        "meta": {
            "model_version": model_version,
            "fallback_reason": "none",
            "confidence_bucket": confidence_bucket,
        },
    }


def predict_injury_risk_from_firestore(user_id: str, date_key: str) -> dict[str, Any]:
    """
    Single-source serving path: load all relevant inputs from Firestore and run
    standard production prediction.
    """
    snapshot = fetch_daily_firestore_snapshot(user_id, date_key)
    if not snapshot:
        raise ValueError("firestore_snapshot_unavailable")

    profile = snapshot.get("profile") or {}
    health = snapshot.get("daily_health") or {}
    checkins = snapshot.get("daily_checkins") or {}
    nutrition = snapshot.get("daily_nutrition") or {}

    payload = InjuryPredictionRequest(
        userId=user_id,
        date=date_key,
        age=profile.get("age"),
        vo2_max=profile.get("vo2Max") or profile.get("vo2_max"),
        history_injury_count=profile.get("historyInjuryCount") or profile.get("history_injury_count"),
        sleepMinutes=health.get("sleepMinutes"),
        steps=health.get("steps"),
        distanceMeters=health.get("distanceMeters"),
        activeCalories=health.get("activeCalories"),
        totalCalories=health.get("totalCalories"),
        heartRateAvg=health.get("heartRateAvg"),
        heartRateMax=health.get("heartRateMax"),
        heartRateMin=health.get("heartRateMin"),
        weightKg=health.get("weightKg"),
        bmrCalories=health.get("bmrCalories"),
        energyLevel=checkins.get("energyLevel"),
        muscleSoreness=checkins.get("muscleSoreness"),
        stressLevel=checkins.get("stressLevel"),
        totalProtein=nutrition.get("totalProtein"),
        totalCarbs=nutrition.get("totalCarbs"),
        mealsLoggedCount=nutrition.get("mealsLoggedCount"),
    )
    return predict_injury_risk(payload)


def persist_prediction_result_or_raise(
    user_id: str,
    date_key: str,
    result: dict[str, Any],
    source: str,
) -> None:
    ok = save_daily_prediction_result(user_id, date_key, result, source=source)
    if not ok:
        raise RuntimeError("prediction_persist_failed")
