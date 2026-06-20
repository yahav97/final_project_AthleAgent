"""
Temporary Firestore explorer — read-only. Delete when you no longer need it.

Run from repo root or backend dir (use the backend venv so firebase-admin is installed):
  cd backend && .\\venv\\Scripts\\activate   # Windows
  python scripts/introspect_firestore.py
  python scripts/introspect_firestore.py --user-id YOUR_UID --max-daily 5 --debug

Uses the same credentials as the API (config / FIREBASE_SERVICE_ACCOUNT_KEY / firebase-key.json).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _value_kind(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, bytes):
        return "bytes"
    if isinstance(value, list):
        if not value:
            return "list[empty]"
        inner = {_value_kind(x) for x in value[:5]}
        extra = len(value) - 5 if len(value) > 5 else 0
        suffix = f"+{extra} more" if extra > 0 else ""
        return f"list[{', '.join(sorted(inner))}{suffix}]"
    if isinstance(value, dict):
        return f"map({len(value)} keys)"
    return type(value).__name__


def _print_doc_fields(label: str, data: dict[str, Any] | None, indent: str = "  ") -> None:
    if not data:
        print(f"{indent}{label}: <missing or empty>")
        return
    print(f"{indent}{label}:")
    for key in sorted(data.keys()):
        print(f"{indent}  {key}: {_value_kind(data[key])} = {_preview(data[key])}")


def _preview(value: Any, max_len: int = 80) -> str:
    if isinstance(value, dict):
        return "{...}"
    if isinstance(value, list):
        return "[...]" if len(value) > 8 else json.dumps(value, default=str)
    s = json.dumps(value, default=str)
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


def main() -> int:
    parser = argparse.ArgumentParser(description="Print Firestore paths, field names, and value kinds (read-only).")
    parser.add_argument("--max-users", type=int, default=3, help="Max user documents to scan under users/")
    parser.add_argument("--max-daily", type=int, default=2, help="Max daily docs per subcollection per user")
    parser.add_argument("--user-id", type=str, default=None, help="Inspect only this Firebase Auth uid (deep dive)")
    parser.add_argument("--teams", type=int, default=3, help="Max team documents to scan (0=skip)")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print underlying exception if Firestore client initialization fails.",
    )
    args = parser.parse_args()

    from config import settings
    from services.history_service import _get_firestore_client

    cred = settings.FIREBASE_SERVICE_ACCOUNT_KEY or settings.GOOGLE_APPLICATION_CREDENTIALS
    print("--- Credentials (path only) ---")
    print(f"  FIREBASE_SERVICE_ACCOUNT_KEY / GOOGLE_APPLICATION_CREDENTIALS: {cred or '<not set — init may fail>'}")
    print()

    db = _get_firestore_client()
    if db is None and args.debug:
        try:
            import firebase_admin
            from firebase_admin import credentials as fb_cred
            from firebase_admin import firestore as fb_firestore

            if cred and Path(cred).is_file():
                c = fb_cred.Certificate(str(cred))
                if not firebase_admin._apps:
                    firebase_admin.initialize_app(c)
                db = fb_firestore.client()
            else:
                print(f"DEBUG: credential path missing or not a file: {cred!r}")
        except Exception as exc:
            print(f"DEBUG: init failed: {type(exc).__name__}: {exc}")

    if db is None:
        print("ERROR: Could not create Firestore client. Use --debug for details; ensure backend venv + firebase-admin.")
        return 1

    if args.user_id:
        print(f"=== Single user: {args.user_id} ===\n")
        uref = db.collection("users").document(args.user_id)
        udoc = uref.get()
        if not udoc.exists:
            print(f"  users/{args.user_id}: <document does not exist>")
            return 0
        _print_doc_fields(f"path users/{args.user_id}", udoc.to_dict())

        for sub, title in (
            ("daily_health", "daily_health"),
            ("daily_checkins", "daily_checkins"),
            ("daily_nutrition", "daily_nutrition"),
        ):
            print(f"\n  --- Subcollection {sub} (up to {args.max_daily} docs) ---")
            q = uref.collection(sub).order_by("__name__").limit(args.max_daily)
            found = list(q.stream())
            if not found:
                print(f"    <no documents>")
                continue
            for snap in found:
                _print_doc_fields(f"path {snap.reference.path}", snap.to_dict(), indent="    ")
                if sub == "daily_nutrition":
                    meals = list(snap.reference.collection("meals").limit(2).stream())
                    if meals:
                        print(f"    meals (sample {len(meals)}):")
                        for m in meals:
                            _print_doc_fields(f"path {m.reference.path}", m.to_dict(), indent="      ")
        return 0

    print("=== Collection: users ===\n")
    users_q = db.collection("users").limit(args.max_users)
    user_docs = list(users_q.stream())
    if not user_docs:
        print("  <no user documents>")
    for udoc in user_docs:
        uid = udoc.id
        data = udoc.to_dict() or {}
        print(f"path users/{uid}")
        _print_doc_fields("profile", data, indent="  ")

        uref = udoc.reference
        for sub in ("daily_health", "daily_checkins", "daily_nutrition"):
            snaps = list(uref.collection(sub).order_by("__name__").limit(args.max_daily).stream())
            print(f"  {sub}: {len(snaps)} sample doc id(s): {[s.id for s in snaps]}")
            for snap in snaps:
                keys = sorted((snap.to_dict() or {}).keys())
                print(f"    {sub}/{snap.id} fields ({len(keys)}): {keys}")
        print()

    if args.teams > 0:
        print(f"=== Collection: teams (limit {args.teams}) ===\n")
        tdocs = list(db.collection("teams").limit(args.teams).stream())
        if not tdocs:
            print("  <no team documents>")
        for tdoc in tdocs:
            _print_doc_fields(f"path {tdoc.reference.path}", tdoc.to_dict(), indent="  ")
            reqs = list(tdoc.reference.collection("requests").limit(3).stream())
            if reqs:
                print(f"  requests (sample {len(reqs)}):")
                for r in reqs:
                    print(f"    {r.reference.path}: {sorted((r.to_dict() or {}).keys())}")
            print()

    print("--- Done (read-only) ---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
