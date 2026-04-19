"""API route modules.

Avoid importing legacy ``auth`` here so ``ENABLE_LEGACY_AUTH_DB=false`` does not
pull SQLAlchemy/Postgres. Import ``api.routes.auth`` only from ``main`` when needed.
"""

__all__ = ["auth", "health", "predict"]
