"""Entraînement du modèle de prédiction géospatiale — délègue à prediction_shared."""

from __future__ import annotations

from pathlib import Path

from prediction_shared.training import run_training_pipeline


def train_gradient_boosting_classifier(
    csv_path: str | Path,
    model_path: str | Path,
    scaler_path: str | Path,
    *,
    n_estimators: int = 100,
) -> dict:
    """
    Entraîne via le pipeline complet (CV + sélection modèle).
    Les chemins csv/model/scaler sont dérivés du répertoire prediction si présents.
    """
    del n_estimators  # hyperparamètres gérés dans prediction_shared.training
    base = Path(csv_path).resolve().parent.parent
    summary = run_training_pipeline(base, rebuild_splits=True)
    return {
        "status": summary.get("status", "trained"),
        "algorithm": summary.get("algorithm"),
        "samples_used": summary.get("samples", {}).get("fit_total", 0),
        "class_distribution": summary.get("class_distribution", {}).get("full", {}),
        "model_path": summary.get("model_path", str(model_path)),
        "scaler_path": summary.get("scaler_path", str(scaler_path)),
        "selection_reason": summary.get("selection_reason"),
        "test_metrics": summary.get("test_metrics"),
        "gold_metrics": summary.get("gold_metrics"),
    }


def default_prediction_paths(base_dir: str | Path | None = None) -> tuple[Path, Path, Path]:
    from django.conf import settings

    root = Path(base_dir or settings.BASE_DIR) / "prediction"
    return (
        root / "data" / "data_reports.csv",
        root / "model" / "best_model.pkl",
        root / "model" / "scaler.pkl",
    )


def train_default_model() -> dict:
    csv_path, model_path, scaler_path = default_prediction_paths()
    return train_gradient_boosting_classifier(csv_path, model_path, scaler_path)
