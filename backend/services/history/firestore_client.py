"""Firebase Admin SDK client singleton."""

from __future__ import annotations

from config import settings


def get_firestore_client():
    """Initialize Firebase Admin SDK and return Firestore client."""
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except Exception:
        return None

    if not firebase_admin._apps:
        cred_path = settings.FIREBASE_SERVICE_ACCOUNT_KEY or settings.GOOGLE_APPLICATION_CREDENTIALS
        try:
            if cred_path:
                cred = credentials.Certificate(str(cred_path))
                firebase_admin.initialize_app(cred)
            else:
                firebase_admin.initialize_app()
        except Exception:
            return None
    try:
        return firestore.client()
    except Exception:
        return None
