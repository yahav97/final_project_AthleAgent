import json
from pathlib import Path

import joblib

from ml import model_loader


def _write_bundle(path: Path) -> None:
    joblib.dump(
        {
            "estimator": object(),
            "feature_columns": ["age", "sleep_hours"],
            "threshold": 0.35,
            "medium_threshold": 0.2,
            "winner": "ExtraTrees",
        },
        path,
    )


def test_load_model_rejects_corrupted_manifest(tmp_path):
    model_path = tmp_path / "injury_model.pkl"
    manifest_path = tmp_path / "run_manifest.json"
    _write_bundle(model_path)
    manifest_path.write_text("{ bad json", encoding="utf-8")

    out = model_loader.load_model(str(model_path), str(manifest_path))
    assert out is None
    assert model_loader.get_model_gate_reason() == "manifest_corrupted"


def test_load_model_rejects_manifest_below_recall_gate(tmp_path):
    model_path = tmp_path / "injury_model.pkl"
    manifest_path = tmp_path / "run_manifest.json"
    _write_bundle(model_path)
    manifest = {
        "winner": "ExtraTrees",
        "policy": {"recall_hard_min": 0.85},
        "winner_metrics": {
            "Recall@Threshold": 0.80,
            "ROC-AUC": 0.72,
        },
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    out = model_loader.load_model(str(model_path), str(manifest_path))
    assert out is None
    assert model_loader.get_model_gate_reason() == "manifest_recall_below_hard_gate"


def test_load_model_rejects_manifest_below_auc_gate(tmp_path):
    model_path = tmp_path / "injury_model.pkl"
    manifest_path = tmp_path / "run_manifest.json"
    _write_bundle(model_path)
    manifest = {
        "winner": "ExtraTrees",
        "policy": {"recall_hard_min": 0.85},
        "winner_metrics": {
            "Recall@Threshold": 0.90,
            "ROC-AUC": 0.55,
        },
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    out = model_loader.load_model(str(model_path), str(manifest_path))
    assert out is None
    assert model_loader.get_model_gate_reason() == "manifest_auc_too_low"
