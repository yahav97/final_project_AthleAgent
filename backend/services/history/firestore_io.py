"""Firestore client, field projections, and document read helpers."""

from __future__ import annotations

from typing import Any

from config import settings
from utils.logging import logger

PROFILE_INFERENCE_FIELDS: tuple[str, ...] = (
    "birth_date",
    "historyInjuryCount",
)

DAILY_HEALTH_INFERENCE_FIELDS: tuple[str, ...] = (
    "sleepMinutes",
    "injuredYesterday",
    "steps",
    "distanceMeters",
    "activeCalories",
    "totalCalories",
    "heartRateAvg",
    "heartRateMax",
    "heartRateMin",
    "weightKg",
    "heightCm",
    "bmrCalories",
    "hrvRmssd",
    "restingHeartRate",
    "bodyFatPct",
    "vo2Max",
    "elevationGainedMeters",
    "floorsClimbed",
    "avgSpeed",
    "maxSpeed",
    "avgPower",
    "avgCadence",
    "respiratoryRate",
    "oxygenSaturation",
)

DAILY_CHECKIN_INFERENCE_FIELDS: tuple[str, ...] = (
    "energyLevel",
    "muscleSoreness",
    "stressLevel",
    "injuredYesterday",
)

DAILY_NUTRITION_INFERENCE_FIELDS: tuple[str, ...] = (
    "totalProtein",
    "totalCarbs",
    "mealsLoggedCount",
    "totalCalories",
)

INFERENCE_FIELD_PATHS: tuple[str, ...] = tuple(
    sorted(
        {
            *PROFILE_INFERENCE_FIELDS,
            *DAILY_HEALTH_INFERENCE_FIELDS,
            *DAILY_CHECKIN_INFERENCE_FIELDS,
            *DAILY_NUTRITION_INFERENCE_FIELDS,
        }
    )
)


def get_firestore_client():
    """Initialize Firebase Admin SDK and return Firestore client."""
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except Exception as exc:
        logger.warning("firebase_admin import failed: %s", exc, exc_info=True)
        return None

    if not firebase_admin._apps:
        cred_path = settings.FIREBASE_SERVICE_ACCOUNT_KEY or settings.GOOGLE_APPLICATION_CREDENTIALS
        try:
            if cred_path:
                cred = credentials.Certificate(str(cred_path))
                firebase_admin.initialize_app(cred)
            else:
                firebase_admin.initialize_app()
        except Exception as exc:
            logger.warning("firebase_admin initialize_app failed: %s", exc, exc_info=True)
            return None
    try:
        return firestore.client()
    except Exception as exc:
        logger.warning("firestore.client() failed: %s", exc, exc_info=True)
        return None


def doc_to_dict(snapshot: Any | None) -> dict[str, Any]:
    """Return ``to_dict()`` for an existing snapshot, else ``{}``."""
    if snapshot is None or not getattr(snapshot, "exists", False):
        return {}
    return snapshot.to_dict() or {}


def read_firestore_document(doc_ref: Any, field_paths: tuple[str, ...] | None = None) -> Any:
    """Sync Firestore document read (firebase_admin client, not async client)."""
    if field_paths:
        return doc_ref.get(field_paths=field_paths)
    return doc_ref.get()


def read_firestore_documents(
    db: Any,
    doc_refs: list[Any],
    *,
    field_paths: tuple[str, ...] | None = None,
) -> list[Any]:
    """
    Batch-read Firestore documents in one round trip when the client supports ``get_all``.

    When ``field_paths`` is set, only those top-level fields are returned per document.
    Falls back to sequential ``doc_ref.get()`` for tests or minimal mocks without ``get_all``.
    """
    if not doc_refs:
        return []
    get_all = getattr(db, "get_all", None)
    if callable(get_all):
        if field_paths:
            return list(get_all(doc_refs, field_paths=field_paths))
        return list(get_all(doc_refs))
    return [read_firestore_document(ref, field_paths=field_paths) for ref in doc_refs]
