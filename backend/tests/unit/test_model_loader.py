"""Unit tests for model_loader manifest gate logic."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pytest

from ml import model_loader

pytestmark = pytest.mark.unit


def _write_valid_bundle(tmp_path: Path) -> tuple[Path, Path]:
    model_path = tmp_path / "injury_model.pkl"
    manifest_path = tmp_path / "run_manifest.json"
    joblib.dump(
        {
            "estimator": object(),
            "feature_columns": ["age", "sleep_hours"],
            "threshold": 0.35,
            "medium_threshold": 0.2,
            "winner": "ExtraTrees",
        },
        model_path,
    )
    manifest = {
        "winner": "ExtraTrees",
        "policy": {"recall_hard_min": 0.85},
        "winner_metrics": {
            "Recall@Threshold": 0.90,
            "ROC-AUC": 0.72,
        },
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return model_path, manifest_path


class TestLoadModelGate:
    def test_rejects_corrupted_manifest(self, tmp_path):
        model_path, manifest_path = _write_valid_bundle(tmp_path)
        manifest_path.write_text("{ bad json", encoding="utf-8")
        assert model_loader.load_model(model_path, manifest_path) is None
        assert model_loader.get_model_gate_reason() == "manifest_corrupted"

    def test_rejects_recall_below_hard_gate(self, tmp_path):
        model_path = tmp_path / "injury_model.pkl"
        manifest_path = tmp_path / "run_manifest.json"
        joblib.dump({"estimator": object()}, model_path)
        manifest = {
            "winner": "ExtraTrees",
            "policy": {"recall_hard_min": 0.85},
            "winner_metrics": {"Recall@Threshold": 0.80, "ROC-AUC": 0.72},
        }
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        assert model_loader.load_model(model_path, manifest_path) is None
        assert model_loader.get_model_gate_reason() == "manifest_recall_below_policy_hard_min"

    def test_rejects_auc_below_gate(self, tmp_path):
        model_path = tmp_path / "injury_model.pkl"
        manifest_path = tmp_path / "run_manifest.json"
        joblib.dump({"estimator": object()}, model_path)
        manifest = {
            "winner": "ExtraTrees",
            "policy": {},
            "winner_metrics": {"Recall@Threshold": 0.90, "ROC-AUC": 0.55},
        }
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        assert model_loader.load_model(model_path, manifest_path) is None
        assert model_loader.get_model_gate_reason() == "manifest_auc_too_low"

    def test_accepts_valid_manifest(self, tmp_path):
        model_path, manifest_path = _write_valid_bundle(tmp_path)
        result = model_loader.load_model(model_path, manifest_path)
        assert result is not None
        assert model_loader.get_model_gate_reason() == "none"
        status = model_loader.get_model_status()
        assert status["status"] == "Live"
        assert status["winner"] == "ExtraTrees"


class TestGetModelStatus:
    def test_blocked_when_not_loaded(self, tmp_path):
        missing = tmp_path / "nonexistent.pkl"
        model_loader.load_model(missing)
        status = model_loader.get_model_status()
        assert status["status"] == "Blocked"
        assert status["gate_reason"] != "none"


class TestPromotedPointerResolution:
    def test_resolves_relative_promoted_path(self, monkeypatch, tmp_path):
        project_root = tmp_path / "proj"
        artifacts = project_root / "ML_model" / "artifacts" / "run1"
        artifacts.mkdir(parents=True)
        model_path, manifest_path = _write_valid_bundle(artifacts)

        promoted_file = project_root / "ML_model" / "artifacts" / "promoted.json"
        promoted_file.write_text(
            json.dumps({"model_path": "ML_model/artifacts/run1/injury_model.pkl"}),
            encoding="utf-8",
        )

        monkeypatch.setattr(model_loader, "_project_root", lambda: project_root)
        result = model_loader.load_model()
        assert result is not None
        assert model_loader.get_model_gate_reason() == "none"

    def test_falls_back_when_promoted_path_missing(self, monkeypatch, tmp_path):
        project_root = tmp_path / "proj"
        promoted_dir = project_root / "ML_model" / "artifacts"
        promoted_dir.mkdir(parents=True)
        promoted_file = promoted_dir / "promoted.json"
        promoted_file.write_text(
            json.dumps({"model_path": "ML_model/artifacts/missing/injury_model.pkl"}),
            encoding="utf-8",
        )

        backend_dir = project_root / "backend"
        backend_dir.mkdir()
        fallback_model, manifest_path = _write_valid_bundle(backend_dir)
        manifest_path.unlink()

        monkeypatch.setattr(model_loader, "_project_root", lambda: project_root)
        monkeypatch.setattr(model_loader, "_fallback_model_path", lambda: fallback_model)
        result = model_loader.load_model()
        assert result is not None
        assert model_loader.get_model_gate_reason() == "none"
        assert model_loader.get_model_status()["status"] == "Live"
