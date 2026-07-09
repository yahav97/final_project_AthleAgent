"""Validate first-iteration policy metrics from model_comparison.csv."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pandas as pd

from policy_config import get_policy


def _latest_artifacts_dir(script_dir: str) -> str | None:
    root = Path(script_dir) / "artifacts"
    if not root.exists():
        return None
    candidates = [p for p in root.iterdir() if p.is_dir()]
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.name, reverse=True)
    return str(candidates[0])


def _load_manifest(manifest_path: str) -> dict | None:
    if not os.path.exists(manifest_path):
        return None
    try:
        with open(manifest_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate promoted model metrics.")
    parser.add_argument(
        "--allow-cv-disagreement",
        action="store_true",
        help="Allow promotion when CV top model differs from selected holdout winner.",
    )
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    artifacts_dir = _latest_artifacts_dir(script_dir) or script_dir
    comparison_path = os.path.join(artifacts_dir, "model_comparison.csv")
    manifest_path = os.path.join(artifacts_dir, "run_manifest.json")
    if not os.path.exists(comparison_path):
        print("model_comparison.csv not found. Run train_model.py first.")
        return 1

    df = pd.read_csv(comparison_path)
    required_columns = {
        "Model",
        "Recall@Threshold",
        "Precision@Threshold",
        "F1@Threshold",
        "FPR@Threshold",
        "BrierScore",
        "ROC-AUC",
        "LogLoss",
    }
    missing = required_columns - set(df.columns)
    if missing:
        print(f"model_comparison.csv missing columns: {sorted(missing)}")
        return 1

    manifest = _load_manifest(manifest_path)
    top = None
    if manifest:
        winner = str(manifest.get("winner") or "").strip()
        wm = manifest.get("winner_metrics") or {}
        if winner and wm:
            top = {
                "Model": winner,
                "Recall@Threshold": float(wm.get("Recall@Threshold")),
                "Precision@Threshold": float(wm.get("Precision@Threshold")),
                "F1@Threshold": float(wm.get("F1@Threshold")),
                "FPR@Threshold": float(wm.get("FPR@Threshold")),
                "ROC-AUC": float(wm.get("ROC-AUC")),
                "BrierScore": float(wm.get("BrierScore")),
                "LogLoss": float(wm.get("LogLoss")),
            }
            print(
                "Policy source: run_manifest winner metrics "
                f"(operating threshold={manifest.get('threshold')})"
            )

    if manifest:
        protocol = manifest.get("selection_protocol") or {}
        cv_agreement = protocol.get("cv_holdout_agreement")
        if cv_agreement and cv_agreement.get("agreement") is False:
            print(
                "\nCV/holdout disagreement: "
                f"CV top={cv_agreement.get('cv_top_model')}, "
                f"selected={cv_agreement.get('selected_model', cv_agreement.get('holdout_winner'))}, "
                f"holdout-only={cv_agreement.get('holdout_pure_winner', '—')}."
            )
            if not args.allow_cv_disagreement:
                print(
                    "REJECTED: promotion blocked because cv_holdout_agreement=false. "
                    "Re-train or pass --allow-cv-disagreement to override."
                )
                return 1
            print("NOTE: continuing because --allow-cv-disagreement was set.")

    if top is None:
        policy = get_policy()
        gated = df[df["Recall@Threshold"] >= policy.MIN_RECALL_HARD]
        ranked_base = gated if not gated.empty else df
        ranked = ranked_base.sort_values(
            by=[
                "FPR@Threshold",
                "Recall@Threshold",
                "F1@Threshold",
                "Precision@Threshold",
                "BrierScore",
                "ROC-AUC",
            ],
            ascending=[True, False, False, False, True, False],
        )
        print(f"Policy threshold: {policy.THRESHOLD}")
        print(ranked.to_string(index=False))
        top = ranked.iloc[0].to_dict()

    policy = get_policy()
    recall_value = float(top["Recall@Threshold"])
    recall_hard_gate_ok = recall_value >= policy.MIN_RECALL_HARD
    recall_target_ok = recall_value >= policy.TARGET_RECALL
    fpr_ok = float(top["FPR@Threshold"]) <= policy.MAX_FPR_OPERATING
    auc_ok = float(top["ROC-AUC"]) >= policy.MIN_AUC_FOR_LIVE
    precision_ok = float(top["Precision@Threshold"]) >= policy.TARGET_PRECISION
    f1_ok = float(top["F1@Threshold"]) >= policy.TARGET_F1
    if not recall_hard_gate_ok:
        print(
            f"\nREJECTED: {top['Model']} failed hard safety gate "
            f"(Recall={recall_value:.4f} < {policy.MIN_RECALL_HARD})."
        )
        return 1

    if recall_target_ok and fpr_ok and auc_ok and precision_ok and f1_ok:
        print(
            f"\nPASS: {top['Model']} meets targets "
            f"(Recall>={policy.TARGET_RECALL}, FPR<={policy.MAX_FPR_OPERATING}, "
            f"AUC>={policy.MIN_AUC_FOR_LIVE}, Precision>={policy.TARGET_PRECISION}, "
            f"F1>={policy.TARGET_F1}). "
            f"Hard gate: Recall>={policy.MIN_RECALL_HARD}."
        )
        return 0

    print(
        f"\nWARN: Top model {top['Model']} does not meet all targets "
        f"(Recall>={policy.TARGET_RECALL}, FPR<={policy.MAX_FPR_OPERATING}, "
        f"AUC>={policy.MIN_AUC_FOR_LIVE}, Precision>={policy.TARGET_PRECISION}, "
        f"F1>={policy.TARGET_F1}) "
        f"but passes hard gate Recall>={policy.MIN_RECALL_HARD}."
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
