"""Run full ML pipeline and promote latest successful artifact set."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _run(command: list[str], cwd: Path, allowed_exit_codes: tuple[int, ...] = (0,)) -> int:
    proc = subprocess.run(command, cwd=str(cwd), check=False, capture_output=True, text=True)
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    if proc.returncode not in allowed_exit_codes:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(command)}")
    return proc.returncode


def _latest_artifacts_dir(ml_dir: Path) -> Path:
    artifacts_root = ml_dir / "artifacts"
    dirs = sorted([p for p in artifacts_root.iterdir() if p.is_dir()], key=lambda p: p.name, reverse=True)
    if not dirs:
        raise RuntimeError("No artifacts directories produced by training.")
    return dirs[0]


def _promote(ml_dir: Path, artifacts_dir: Path, degraded_rc: bool) -> None:
    promoted_path = ml_dir / "artifacts" / "promoted.json"
    payload = {
        "artifacts_dir": str(artifacts_dir),
        "model_path": str(artifacts_dir / "injury_model.pkl"),
        "manifest_path": str(artifacts_dir / "run_manifest.json"),
        "degraded_rc": degraded_rc,
    }
    with open(promoted_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"Promoted artifact set: {artifacts_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AthleAgent ML pipeline.")
    parser.add_argument("--num-athletes", type=int, default=1000)
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--force-benchmark", action="store_true")
    args = parser.parse_args()

    ml_dir = Path(__file__).resolve().parent
    _run(
        [
            sys.executable,
            "data_generator.py",
            "--num-athletes",
            str(args.num_athletes),
            "--days",
            str(args.days),
            "--seed",
            str(args.seed),
        ],
        ml_dir,
    )
    benchmark_cmd = [sys.executable, "create_benchmark_set.py", "--seed", str(args.seed)]
    if args.force_benchmark:
        benchmark_cmd.append("--force")
    _run(benchmark_cmd, ml_dir)
    _run([sys.executable, "train_model.py"], ml_dir)
    validate_exit = _run([sys.executable, "validate_metrics.py"], ml_dir, allowed_exit_codes=(0, 2))
    artifacts_dir = _latest_artifacts_dir(ml_dir)
    _promote(ml_dir, artifacts_dir, degraded_rc=(validate_exit == 2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
