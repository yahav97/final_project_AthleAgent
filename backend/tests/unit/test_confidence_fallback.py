"""Unit tests for history confidence parsing and rolling-feature fallback."""

from __future__ import annotations

import pandas as pd
import pytest

from schemas.enums import HistoryConfidence
from schemas.inference import InjuryPredictionRequest
from services.model_features import DEFAULT_FEATURE_VALUES
from services.prediction.confidence import (
    HISTORY_ROLLING_FEATURES,
    apply_history_confidence_fallback,
    parse_history_confidence,
)
from services.preprocessing import injury_request_to_model_dataframe

pytestmark = pytest.mark.unit

_HISTORY_FEATURES = {
    "acute_load_7d": 5.2,
    "acwr_ratio": 1.45,
    "acwr_ratio_ma7": 1.38,
    "sleep_hours_ma7": 6.8,
    "sleep_debt_3d": 0.6,
    "hrv_drop": -2.1,
}


def _base_frame() -> pd.DataFrame:
    return injury_request_to_model_dataframe(
        InjuryPredictionRequest(
            userId="u1",
            date="2026-04-30",
            age=28,
            sleepMinutes=420,
            steps=5000,
            stressLevel=40,
            muscleSoreness=3,
            energyLevel=70,
        )
    )


class TestParseHistoryConfidence:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (HistoryConfidence.HIGH, HistoryConfidence.HIGH),
            ("high", HistoryConfidence.HIGH),
            ("medium", HistoryConfidence.MEDIUM),
            ("low", HistoryConfidence.LOW),
            ("unknown", HistoryConfidence.LOW),
            ("", HistoryConfidence.LOW),
        ],
    )
    def test_normalizes_valid_and_invalid_labels(self, raw, expected):
        assert parse_history_confidence(raw) == expected


class TestApplyHistoryConfidenceFallback:
    def test_skips_firestore_when_user_or_date_missing(self, monkeypatch):
        called = {"fetch": False}

        def _should_not_call(*args, **kwargs):
            called["fetch"] = True
            return {}

        monkeypatch.setattr(
            "services.prediction.confidence.get_history_window_context",
            _should_not_call,
        )
        frame = _base_frame()
        out, confidence = apply_history_confidence_fallback(
            frame,
            InjuryPredictionRequest(userId="", date="2026-04-30", age=28),
        )

        assert called["fetch"] is False
        assert confidence == HistoryConfidence.LOW

    def test_high_confidence_injects_history_rolling_features(self, monkeypatch):
        monkeypatch.setattr(
            "services.prediction.confidence.get_history_window_context",
            lambda *a, **k: {"confidence": "high", "features": dict(_HISTORY_FEATURES)},
        )
        payload = InjuryPredictionRequest(
            userId="u1",
            date="2026-04-30",
            age=28,
            sleepMinutes=420,
            steps=5000,
            stressLevel=40,
            muscleSoreness=3,
            energyLevel=70,
        )
        out, confidence = apply_history_confidence_fallback(_base_frame(), payload)

        assert confidence == HistoryConfidence.HIGH
        for column, value in _HISTORY_FEATURES.items():
            assert float(out[column].iloc[0]) == pytest.approx(value)

    def test_medium_confidence_injects_history_rolling_features(self, monkeypatch):
        monkeypatch.setattr(
            "services.prediction.confidence.get_history_window_context",
            lambda *a, **k: {"confidence": "medium", "features": dict(_HISTORY_FEATURES)},
        )
        payload = InjuryPredictionRequest(userId="u1", date="2026-04-30", age=28)
        out, confidence = apply_history_confidence_fallback(_base_frame(), payload)

        assert confidence == HistoryConfidence.MEDIUM
        assert float(out["acwr_ratio"].iloc[0]) == pytest.approx(1.45)

    def test_low_confidence_resets_rolling_features_to_population_defaults(self, monkeypatch):
        monkeypatch.setattr(
            "services.prediction.confidence.get_history_window_context",
            lambda *a, **k: {
                "confidence": "low",
                "features": dict(_HISTORY_FEATURES),
            },
        )
        payload = InjuryPredictionRequest(userId="u1", date="2026-04-30", age=28)
        frame = _base_frame()
        out, confidence = apply_history_confidence_fallback(frame, payload)

        assert confidence == HistoryConfidence.LOW
        for column in HISTORY_ROLLING_FEATURES:
            assert float(out[column].iloc[0]) == pytest.approx(
                float(DEFAULT_FEATURE_VALUES[column])
            )

    def test_low_confidence_without_features_uses_defaults(self, monkeypatch):
        monkeypatch.setattr(
            "services.prediction.confidence.get_history_window_context",
            lambda *a, **k: {"confidence": "low", "features": None},
        )
        payload = InjuryPredictionRequest(userId="u1", date="2026-04-30", age=28)
        out, confidence = apply_history_confidence_fallback(_base_frame(), payload)

        assert confidence == HistoryConfidence.LOW
        for column in HISTORY_ROLLING_FEATURES:
            assert float(out[column].iloc[0]) == pytest.approx(
                float(DEFAULT_FEATURE_VALUES[column])
            )

    def test_high_confidence_without_features_falls_back_to_defaults(self, monkeypatch):
        monkeypatch.setattr(
            "services.prediction.confidence.get_history_window_context",
            lambda *a, **k: {"confidence": "high", "features": {}},
        )
        payload = InjuryPredictionRequest(userId="u1", date="2026-04-30", age=28)
        out, confidence = apply_history_confidence_fallback(_base_frame(), payload)

        assert confidence == HistoryConfidence.HIGH
        for column in HISTORY_ROLLING_FEATURES:
            assert float(out[column].iloc[0]) == pytest.approx(
                float(DEFAULT_FEATURE_VALUES[column])
            )
