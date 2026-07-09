"""Run full ML pipeline: generate data → train → validate → promote."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_ml_dir = str(Path(__file__).resolve().parent)
if _ml_dir not in sys.path:
    sys.path.insert(0, _ml_dir)

from training.constants import latest_artifacts_dir  # noqa: E402


def _run(command: list[str], cwd: Path) -> None:
    proc = subprocess.run(command, cwd=str(cwd), check=False, capture_output=True, text=True)
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(command)}")


def _require_latest_artifacts_dir(ml_dir: Path) -> Path:
    artifacts_dir = latest_artifacts_dir(ml_dir)
    if artifacts_dir is None:
        raise RuntimeError("No artifacts directories produced by training.")
    return artifacts_dir


def _promote(ml_dir: Path, artifacts_dir: Path) -> None:
    promoted_path = ml_dir / "artifacts" / "promoted.json"
    run_id = artifacts_dir.name
    model_rel = (artifacts_dir / "injury_model.pkl").relative_to(ml_dir.parent).as_posix()
    payload = {
        "model_path": model_rel,
        "run_id": run_id,
        "promoted_at_utc": datetime.now(timezone.utc).isoformat(),
        "promoted_by": "run_pipeline.py",
        "manifest_path": f"ML_model/artifacts/{run_id}/run_manifest.json",
    }
    with open(promoted_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"Promoted artifact set: {artifacts_dir}")


def main() -> int:
    ml_dir = Path(__file__).resolve().parent
    python = sys.executable

    _run([python, "data_generator.py"], ml_dir)
    _run([python, "create_benchmark_set.py"], ml_dir)
    _run([python, "train_model.py"], ml_dir)
    _run([python, "validate_metrics.py"], ml_dir)

    _promote(ml_dir, _require_latest_artifacts_dir(ml_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
