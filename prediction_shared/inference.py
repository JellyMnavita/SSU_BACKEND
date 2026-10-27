"""Chargement modèle, prédiction point et grille — partagé backend / microservice."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

from prediction_shared.dataset import production_model_dir, raw_csv_path, resolve_prediction_data_dir
from prediction_shared.features import engineer_feature_matrix
from prediction_shared.grid import (
    build_kinshasa_sectors,
    build_legend,
    build_prediction_grid,
    compute_risk_scores,
    filter_heatmap_points,
    load_reports_dataframe,
    serialize_grid_points,
)
from prediction_shared.labels import DEGREE_LABEL_MAP, FEATURE_NAMES, RADIUS_KM

logger = logging.getLogger(__name__)

RISK_LABELS = {0: "faible", 1: "modere", 2: "eleve"}
PREDICTION_MAP = {0: "safe", 1: "moderate", 2: "dangerous"}
# Colonnes brutes dans la grille (avant engineering) — sans degré (cible)
RAW_GRID_COLUMNS = [
    "latitude_report",
    "longitude_report",
    "hour",
    "day_of_week",
    "density",
    "nearest_neighbor_km",
]
FEATURE_COLUMNS = list(FEATURE_NAMES)


def _predict_proba(model: Any, X: np.ndarray) -> np.ndarray:
    """Compatibilité modèles sklearn avec ou sans predict_proba (ex. SVC ancien)."""
    if hasattr(model, "predict_proba"):
        return model.predict_proba(X)

    if hasattr(model, "decision_function"):
        scores = model.decision_function(X)
        if scores.ndim == 1:
            scores = np.column_stack([-scores, scores])
        scores = scores - scores.max(axis=1, keepdims=True)
        exp = np.exp(scores)
        return exp / exp.sum(axis=1, keepdims=True)

    preds = model.predict(X)
    classes = getattr(model, "classes_", np.unique(preds))
    proba = np.zeros((len(preds), len(classes)), dtype=float)
    for idx, label in enumerate(preds):
        class_idx = int(np.where(classes == label)[0][0])
        proba[idx, class_idx] = 1.0
    return proba


def _resolve_paths(
    data_dir: Path | None = None,
) -> tuple[Path, Path, Path]:
    root = data_dir or resolve_prediction_data_dir()
    model_dir = production_model_dir(root)
    return (
        raw_csv_path(root),
        model_dir / "best_model.pkl",
        model_dir / "scaler.pkl",
    )


def clear_assets_cache() -> None:
    load_assets.cache_clear()


@lru_cache(maxsize=1)
def load_assets(data_dir_key: str = "") -> tuple[pd.DataFrame, BallTree, Any, Any]:
    root = Path(data_dir_key) if data_dir_key else resolve_prediction_data_dir()
    csv_path, model_path, scaler_path = _resolve_paths(root)
    if not csv_path.is_file():
        raise FileNotFoundError(f"Dataset introuvable: {csv_path}")
    if not model_path.is_file() or not scaler_path.is_file():
        raise FileNotFoundError(
            f"Modèle introuvable — entraînez d'abord ({model_path}, {scaler_path})"
        )

    df = load_reports_dataframe(str(csv_path))
    coords_rad = np.radians(df[["latitude_report", "longitude_report"]].to_numpy())
    tree = BallTree(coords_rad, metric="haversine")
    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    return df, tree, model, scaler


def compute_density_and_nearest(
    lat: float,
    lon: float,
    df: pd.DataFrame,
    tree: BallTree,
) -> tuple[int, float, float]:
    """Retourne (density, nearest_km, mean_degree_contexte).

    mean_degree est un indicateur d'affichage uniquement — jamais une feature ML.
    """
    point_rad = np.radians([[lat, lon]])
    radius_rad = RADIUS_KM / 6371.0
    indices = tree.query_radius(point_rad, r=radius_rad)[0]
    density = int(len(indices))
    mean_degree = float(df.iloc[indices]["degree_report"].mean()) if density > 0 else 0.0
    dists, _ = tree.query(point_rad, k=1)
    nearest_km = float(dists[0][0] * 6371.0)
    return density, nearest_km, mean_degree


def predict_point(
    lat: float,
    lon: float,
    hour: int = 14,
    day_of_week: int = 2,
    *,
    density: float | None = None,
    mean_degree_danger: float | None = None,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    root = data_dir or resolve_prediction_data_dir()
    df, tree, model, scaler = load_assets(str(root))

    computed_density, nearest_km, computed_mean = compute_density_and_nearest(
        lat, lon, df, tree
    )
    density = computed_density if density is None else int(density)
    # Contexte affichage uniquement (pas en entrée du modèle)
    mean_degree_danger = (
        computed_mean if mean_degree_danger is None else float(mean_degree_danger)
    )

    input_raw = np.array(
        [[lat, lon, hour, day_of_week, density, nearest_km]], dtype=float
    )
    input_data = engineer_feature_matrix(input_raw)
    probas = _predict_proba(model, scaler.transform(input_data))[0]
    prediction = int(np.argmax(probas))
    confidence = float(np.max(probas))
    density_factor = min(float(density) / 8.0, 1.0)
    risk_score = min(
        1.0,
        float(probas[1]) * 0.45
        + float(probas[2]) * 0.95
        + density_factor * 0.25,
    )

    return {
        "latitude": float(lat),
        "longitude": float(lon),
        "hour": hour,
        "day_of_week": day_of_week,
        "density": int(density),
        "nearest_neighbor_km": round(nearest_km, 4),
        "mean_degree_danger": float(mean_degree_danger),
        "prediction": prediction,
        "prediction_level": PREDICTION_MAP[prediction],
        "label": RISK_LABELS[prediction],
        "confidence": confidence,
        "risk_score": round(risk_score, 4),
        "probabilities": {
            "faible": float(probas[0]),
            "modere": float(probas[1]),
            "eleve": float(probas[2]),
        },
        "proba_0": float(probas[0]),
        "proba_1": float(probas[1]),
        "proba_2": float(probas[2]),
    }


def build_grid_layers(
    hour: int = 14,
    day_of_week: int = 2,
    *,
    grid_size: int = 48,
    include_sectors: bool = True,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    root = data_dir or resolve_prediction_data_dir()
    df, _, model, scaler = load_assets(str(root))
    grid_df = build_prediction_grid(
        df, hour, day_of_week, grid_size=grid_size, use_kinshasa_bounds=True
    )
    X_raw = grid_df[RAW_GRID_COLUMNS].to_numpy(dtype=float)
    X = engineer_feature_matrix(X_raw)
    probas = _predict_proba(model, scaler.transform(X))
    grid_df = compute_risk_scores(grid_df, probas)

    all_points = serialize_grid_points(grid_df)
    heatmap_points = filter_heatmap_points(all_points)
    sectors = build_kinshasa_sectors(grid_df, reports_df=df) if include_sectors else []

    return {
        "meta": {
            "hour": hour,
            "day_of_week": day_of_week,
            "total_points": len(all_points),
            "visible_points": len(heatmap_points),
            "sector_count": len(sectors),
            "grid_size": grid_size,
            "source": "prediction-service",
        },
        "points": all_points,
        "heatmap_points": heatmap_points,
        "sectors": sectors,
        "legend": build_legend(),
    }


def health_info(data_dir: Path | None = None) -> dict[str, Any]:
    try:
        root = data_dir or resolve_prediction_data_dir()
        df, _, model, _ = load_assets(str(root))
        return {
            "status": "ok",
            "model_loaded": model is not None,
            "reports_in_dataset": len(df),
        }
    except Exception as exc:
        return {
            "status": "degraded",
            "model_loaded": False,
            "reports_in_dataset": 0,
            "error": str(exc),
        }


def train_model(data_dir: Path | None = None) -> dict[str, Any]:
    from prediction_shared.training import run_training_pipeline

    root = data_dir or resolve_prediction_data_dir()
    clear_assets_cache()
    summary = run_training_pipeline(root, rebuild_splits=True, tune=True)
    clear_assets_cache()
    return {
        "status": summary.get("status", "trained"),
        "algorithm": summary.get("algorithm"),
        "best_params": summary.get("best_params", {}),
        "samples_used": summary.get("samples", {}).get("fit_total", 0),
        "model_path": summary.get("model_path"),
        "selection_reason": summary.get("selection_reason"),
        "ranking": summary.get("ranking", []),
        "comparison": summary.get("comparison", {}),
        "features": summary.get("features", []),
        "feature_catalog": summary.get("feature_catalog", []),
        "feature_correlations_train": summary.get("feature_correlations_train", []),
        "cleaning": summary.get("cleaning", {}),
        "plain_language": summary.get("plain_language", {}),
        "test_metrics": summary.get("test_metrics", {}),
        "gold_metrics": summary.get("gold_metrics", {}),
        "pipeline": summary.get("pipeline", {}),
        "cv_folds": summary.get("cv_folds"),
    }
