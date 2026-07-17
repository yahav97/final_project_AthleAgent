"""Rewrite legacy artifact metadata to the current manifest / bundle schema."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib

_ml_dir = Path(__file__).resolve().parent
_backend_dir = _ml_dir.parent / "backend"
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))
if str(_ml_dir) not in sys.path:
    sys.path.insert(0, str(_ml_dir))

from ml.manifest import normalize_run_manifest  # noqa: E402
from policy_config import policy_as_dict  # noqa: E402


def normalize_artifact_run(run_dir: Path) -> None:
    manifest_path = run_dir / "run_manifest.json"
    model_path = run_dir / "injury_model.pkl"

    if manifest_path.is_file():
        with manifest_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        normalized = normalize_run_manifest(raw)
        with manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(normalized, handle, indent=2)
            handle.write("\n")
        print(f"Updated manifest: {manifest_path}")

    if model_path.is_file():
        bundle = joblib.load(model_path)
        if isinstance(bundle, dict):
            bundle["policy"] = policy_as_dict()
            joblib.dump(bundle, model_path)
            print(f"Updated bundle policy: {model_path}")


def main() -> int:
    promoted_path = _ml_dir / "artifacts" / "promoted.json"
    if promoted_path.is_file():
        promoted = json.loads(promoted_path.read_text(encoding="utf-8"))
        model_rel = promoted.get("model_path")
        if isinstance(model_rel, str):
            run_dir = (_ml_dir.parent / model_rel).resolve().parent
            if run_dir.is_dir():
                normalize_artifact_run(run_dir)
                return 0

    artifacts_root = _ml_dir / "artifacts"
    run_dirs = sorted(
        (path for path in artifacts_root.iterdir() if path.is_dir()),
        key=lambda path: path.name,
        reverse=True,
    )
    if not run_dirs:
        print("No artifact run directories found.")
        return 1

    normalize_artifact_run(run_dirs[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
