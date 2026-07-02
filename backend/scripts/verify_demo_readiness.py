#!/usr/bin/env python3
"""Pre-exhibition checklist: promoted model artifact exists and passes live gates."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent


def _fail(errors: list[str], message: str) -> None:
    errors.append(message)


def main() -> int:
    errors: list[str] = []

    promoted_path = PROJECT_ROOT / "ML_model" / "artifacts" / "promoted.json"
    if not promoted_path.is_file():
        _fail(errors, f"Missing promotion pointer: {promoted_path}")
    else:
        promoted = json.loads(promoted_path.read_text(encoding="utf-8"))
        model_rel = promoted.get("model_path")
        manifest_rel = promoted.get("manifest_path")
        if not isinstance(model_rel, str) or not model_rel.strip():
            _fail(errors, "promoted.json is missing model_path")
        else:
            model_path = PROJECT_ROOT / model_rel
            if not model_path.is_file():
                _fail(errors, f"Promoted model file not found: {model_path}")

        if not isinstance(manifest_rel, str) or not manifest_rel.strip():
            _fail(errors, "promoted.json is missing manifest_path")
        else:
            manifest_path = PROJECT_ROOT / manifest_rel
            if not manifest_path.is_file():
                _fail(errors, f"Promoted manifest not found: {manifest_path}")

    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    from ml.model_loader import get_model_status, load_model

    load_model()
    status = get_model_status()
    if status.get("status") != "Live":
        _fail(
            errors,
            f"Model is not Live (gate_reason={status.get('gate_reason')}). "
            "Run ML_model/run_pipeline.py or copy backend/injury_model.pkl.",
        )

    if errors:
        print("Demo readiness: FAILED")
        for item in errors:
            print(f"  - {item}")
        return 1

    metrics = status.get("winner_metrics") or {}
    print("Demo readiness: OK")
    print(f"  run_id: {status.get('run_id')}")
    print(f"  winner: {status.get('winner')}")
    print(f"  threshold: {status.get('threshold')}")
    print(f"  recall: {metrics.get('Recall@Threshold')}")
    print(f"  roc_auc: {metrics.get('ROC-AUC')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
