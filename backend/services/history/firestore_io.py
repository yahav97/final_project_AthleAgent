"""Low-level Firestore document read helpers."""

from __future__ import annotations

from typing import Any


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
