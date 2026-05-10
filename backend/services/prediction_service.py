"""Orchestration of preprocessing, features, and model.predict_proba."""

from __future__ import annotations

from typing import Any

from ml.model_loader import get_model, get_model_gate_reason
from schemas.inference import InjuryPredictionRequest
from services.history_service import (
    fetch_daily_firestore_snapshot,
    get_history_window_context,
    merge_nutrition_with_history,
    save_daily_prediction_result,
)
from services.model_features import DEFAULT_FEATURE_VALUES, TRAINING_BASE_FEATURE_COLUMNS
from services.preprocessing import (
    calculate_data_quality_score,
    injury_request_to_model_dataframe,
    validate_feature_vector_for_model,
)
from utils.logging import logger


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


def _history_score_from_confidence(confidence: str) -> float:
    if confidence == "high":
        return 0.95
    if confidence == "medium":
        return 0.7
    return 0.45


def _prediction_confidence_0_100(history_confidence: str, quality_score: float) -> float:
    """Blend history-window confidence with same-day input completeness (0–1) → 0–100."""
    hs = _history_score_from_confidence(history_confidence)
    combined = 0.6 * hs + 0.4 * float(quality_score)
    return round(min(100.0, max(0.0, combined * 100.0)), 2)


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


def _firestore_doc_heartrate_avg(doc: dict[str, Any]) -> Any:
    """Prefer ``heartRateAvg``; Firestore samples also used ``avgHeartRate``."""
    if not doc:
        return None
    v = doc.get("heartRateAvg")
    if v is not None:
        return v
    return doc.get("avgHeartRate")


def injury_prediction_request_from_firestore_snapshot(
    user_id: str,
    date_key: str,
    snapshot: dict[str, Any],
) -> InjuryPredictionRequest:
    """
    Build the same ``InjuryPredictionRequest`` as the production Firestore path.

    Merge policy matches ``predict_injury_risk_from_firestore`` (sleep/injury flags today;
    load/physiology from yesterday; check-ins today; nutrition today with history backfill).
    """
    health_today = snapshot.get("daily_health") or {}
    health_yesterday = snapshot.get("daily_health_yesterday") or {}
    checkins = snapshot.get("daily_checkins") or {}
    nutrition_raw = snapshot.get("daily_nutrition") or {}
    nutrition = merge_nutrition_with_history(user_id, date_key, nutrition_raw)

    ij_raw = health_today.get("injuredYesterday")
    if ij_raw is None:
        ij_raw = health_today.get("injured_yesterday")

    return InjuryPredictionRequest(
        userId=user_id,
        date=date_key,
        injuredYesterday=_coerce_injured_yesterday(ij_raw),
        sleepMinutes=health_today.get("sleepMinutes"),
        steps=health_yesterday.get("steps"),
        distanceMeters=health_yesterday.get("distanceMeters"),
        activeCalories=health_yesterday.get("activeCalories"),
        totalCalories=health_yesterday.get("totalCalories"),
        heartRateAvg=_firestore_doc_heartrate_avg(health_yesterday),
        heartRateMax=health_yesterday.get("heartRateMax"),
        heartRateMin=health_yesterday.get("heartRateMin"),
        weightKg=health_yesterday.get("weightKg"),
        bmrCalories=health_yesterday.get("bmrCalories"),
        energyLevel=checkins.get("energyLevel"),
        muscleSoreness=checkins.get("muscleSoreness"),
        stressLevel=checkins.get("stressLevel"),
        totalProtein=nutrition.get("totalProtein"),
        totalCarbs=nutrition.get("totalCarbs"),
        mealsLoggedCount=nutrition.get("mealsLoggedCount"),
        nutritionTotalCalories=nutrition.get("totalCalories"),
    )


def training_base_feature_dict_from_request(payload: InjuryPredictionRequest) -> dict[str, float]:
    """
    One training CSV row (base features only): same inference row as production, then drop columns
    recomputed in ``ML_model/train_model.add_sequential_features``.
    """
    df = injury_request_to_model_dataframe(payload)
    df, _ = _apply_history_confidence_fallback(df, payload)
    out: dict[str, float] = {}
    for col in TRAINING_BASE_FEATURE_COLUMNS:
        out[col] = float(df[col].iloc[0])
    return out


def _coerce_injured_yesterday(raw: object) -> int | None:
    if raw is None:
        return None
    if raw is True:
        return 1
    if raw is False:
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def predict_injury_risk(payload: InjuryPredictionRequest) -> dict[str, Any]:
    """
    Run preprocessing → feature row → sklearn ``predict_proba`` (injury positive class).

    If ``injury_model.pkl`` is not present on the server, returns a conservative demo
    response so local development and CI still behave predictably.

    Client is expected to avoid calling until required inputs exist; we do not reject
    on sparse payloads here (nutrition may still be backfilled server-side for Firestore path).
    """
    df = injury_request_to_model_dataframe(payload)
    df, history_confidence = _apply_history_confidence_fallback(df, payload)
    quality = calculate_data_quality_score(payload)
    quality_score = float(quality["score"])
    logger.info(
        "predict_data_quality userId=%s date=%s quality=%.3f sensitive_missing_fields=%s hard_missing=%s",
        payload.userId,
        payload.date,
        quality_score,
        quality.get("sensitive_missing", []),
        quality.get("hard_missing", []),
    )
    prediction_confidence = _prediction_confidence_0_100(history_confidence, quality_score)
    defaulted_critical_count = _count_defaulted_critical_features(df)
    logger.info(
        "predict_confidence_summary userId=%s prediction_confidence=%.2f defaulted_critical=%d",
        payload.userId,
        prediction_confidence,
        defaulted_critical_count,
    )

    loaded_model = get_model()
    (
        model,
        bundle_feature_columns,
        model_threshold,
        medium_threshold,
        _model_version,
        model_status,
    ) = _resolve_model_bundle(loaded_model)
    if model is None:
        gate_reason = get_model_gate_reason()
        blocked_reason = model_status if model_status != "model_not_loaded" else gate_reason
        logger.warning(
            "predict_blocked userId=%s reason=%s prediction_confidence=%.2f",
            payload.userId,
            blocked_reason,
            prediction_confidence,
        )
        raise RuntimeError(f"model_not_live:{blocked_reason}")

    model_contract = {"estimator": model, "feature_columns": bundle_feature_columns}
    X = validate_feature_vector_for_model(df, model_contract)

    proba = float(model.predict_proba(X)[0, 1])
    high_cutoff = float(model_threshold)
    medium_cutoff = min(float(medium_threshold), high_cutoff)
    risk_level = "High" if proba >= high_cutoff else "Medium" if proba >= medium_cutoff else "Low"
    return {
        "risk_level": risk_level,
        "risk_score": round(proba, 4),
        "prediction_confidence": prediction_confidence,
    }


def predict_injury_risk_from_firestore(user_id: str, date_key: str) -> dict[str, Any]:
    """
    Single-source serving path: load inputs from Firestore and run production inference.

    Merge policy:
    - ``daily_health/{date}``: sleep, injuredYesterday (survey), and any same-day-only keys we keep here.
    - ``daily_health/{date-1}``: physical/load metrics (steps, HR, calories, weight, …).
    - ``daily_checkins/{date}``: subjective survey.
    - ``daily_nutrition/{date}``: macros; missing fields filled from prior days via merge_nutrition_with_history.
    """
    snapshot = fetch_daily_firestore_snapshot(user_id, date_key)
    if not snapshot:
        raise ValueError("firestore_snapshot_unavailable")

    payload = injury_prediction_request_from_firestore_snapshot(user_id, date_key, snapshot)
    return predict_injury_risk(payload)


def persist_prediction_result_or_raise(
    user_id: str,
    date_key: str,
    result: dict[str, Any],
) -> None:
    ok = save_daily_prediction_result(user_id, date_key, result)
    if not ok:
        raise RuntimeError("prediction_persist_failed")
