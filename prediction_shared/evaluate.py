"""Évaluation gold et chargement du registre d'entraînement."""

from __future__ import annotations

import json
from pathlib import Path

import joblib

from prediction_shared.dataset import (
    load_gold_eval,
    models_dir,
    production_model_dir,
    resolve_prediction_data_dir,
)
from prediction_shared.features import build_feature_matrix
from prediction_shared.metrics import compute_metrics
from prediction_shared.training import evaluate_on_frame, run_training_pipeline


def _load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_training_summary(data_dir: Path | None = None) -> dict:
    root = data_dir or resolve_prediction_data_dir()
    return _load_json(models_dir(root) / "training_summary.json") or {}


def load_gold_results(data_dir: Path | None = None) -> dict:
    root = data_dir or resolve_prediction_data_dir()
    return _load_json(models_dir(root) / "gold_eval_results.json") or {}


def run_gold_evaluation(data_dir: Path | None = None) -> dict:
    """Évalue le modèle production sur gold_eval (réentraîne si absent)."""
    root = data_dir or resolve_prediction_data_dir()
    gold_df = load_gold_eval(root)
    if gold_df.empty:
        summary = run_training_pipeline(root, rebuild_splits=True)
        return {
            "status": "retrained",
            "metrics": summary.get("gold_metrics") or {},
            "algorithm": summary.get("algorithm"),
            "samples": summary.get("samples", {}).get("gold", 0),
        }

    model_path = production_model_dir(root) / "best_model.pkl"
    scaler_path = production_model_dir(root) / "scaler.pkl"
    if not model_path.is_file() or not scaler_path.is_file():
        summary = run_training_pipeline(root, rebuild_splits=False)
        return {
            "status": "retrained",
            "metrics": summary.get("gold_metrics") or {},
            "algorithm": summary.get("algorithm"),
            "samples": len(gold_df),
        }

    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    metrics = evaluate_on_frame(model, scaler, gold_df)
    result = {
        "status": "evaluated",
        "metrics": metrics,
        "algorithm": load_training_summary(root).get("algorithm"),
        "samples": len(gold_df),
    }
    out = models_dir(root)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "gold_eval_results.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    return result
