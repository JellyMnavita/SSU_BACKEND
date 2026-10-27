"""Grille 48×48, scoring risque et filtrage heatmap — inférence géospatiale."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

from prediction_shared.bounds import KINSHASA_BOUNDS
from prediction_shared.hazards import observed_sector_stats
from prediction_shared.land_mask import is_prediction_land
from prediction_shared.labels import (
    DEGREE_LABEL_MAP,
    KINSHASA_LAT_MAX,
    KINSHASA_LAT_MIN,
    KINSHASA_LON_MAX,
    KINSHASA_LON_MIN,
    RADIUS_KM,
)

DEGREE_TO_INT = DEGREE_LABEL_MAP
RISK_LABELS = {0: "faible", 1: "modéré", 2: "élevé"}
SECTOR_ROWS = 8
SECTOR_COLS = 8


def load_reports_dataframe(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["degree_report"] = df["degree_report"].map(DEGREE_TO_INT).fillna(0).astype(int)
    return df


def build_prediction_grid(
    df: pd.DataFrame,
    hour: int,
    day_of_week: int,
    *,
    grid_size: int = 48,
    use_kinshasa_bounds: bool = True,
) -> pd.DataFrame:
    """Grille régulière : densité et distance au voisin (sans utiliser le degré cible)."""
    if use_kinshasa_bounds:
        bounds = (
            KINSHASA_BOUNDS["min_lon"],
            KINSHASA_BOUNDS["min_lat"],
            KINSHASA_BOUNDS["max_lon"],
            KINSHASA_BOUNDS["max_lat"],
        )
    else:
        lats = df["latitude_report"].astype(float)
        lons = df["longitude_report"].astype(float)
        pad = 0.01
        bounds = (
            float(lons.min()) - pad,
            float(lats.min()) - pad,
            float(lons.max()) + pad,
            float(lats.max()) + pad,
        )

    lats = np.linspace(bounds[1], bounds[3], grid_size)
    lons = np.linspace(bounds[0], bounds[2], grid_size)
    grid_df = pd.DataFrame(
        [(lat, lon) for lat in lats for lon in lons],
        columns=["latitude_report", "longitude_report"],
    )
    grid_df["hour"] = hour
    grid_df["day_of_week"] = day_of_week

    tree = BallTree(
        np.radians(df[["latitude_report", "longitude_report"]].to_numpy()),
        metric="haversine",
    )
    coords_rad = np.radians(grid_df[["latitude_report", "longitude_report"]].to_numpy())
    radius_rad = RADIUS_KM / 6371.0
    indices = tree.query_radius(coords_rad, r=radius_rad)
    nearest_dists, _ = tree.query(coords_rad, k=1)
    nearest_km = (nearest_dists[:, 0] * 6371.0).astype(float)

    densities: list[int] = []
    # Conservé pour affichage / contexte uniquement — PAS une feature ML
    mean_dangers: list[float] = []
    for idx_list in indices:
        density = len(idx_list)
        densities.append(density)
        if density > 0:
            mean_dangers.append(float(df.iloc[idx_list]["degree_report"].mean()))
        else:
            mean_dangers.append(0.0)

    grid_df["density"] = densities
    grid_df["nearest_neighbor_km"] = nearest_km
    grid_df["mean_degree_danger"] = mean_dangers
    grid_df = grid_df[
        grid_df.apply(
            lambda row: is_prediction_land(
                float(row["latitude_report"]), float(row["longitude_report"])
            ),
            axis=1,
        )
    ].reset_index(drop=True)
    return grid_df.fillna(0)


def compute_risk_scores(grid_df: pd.DataFrame, probas: np.ndarray) -> pd.DataFrame:
    grid = grid_df.copy()
    grid["prediction"] = np.argmax(probas, axis=1)
    grid["confidence"] = np.max(probas, axis=1)
    grid["proba_0"] = probas[:, 0]
    grid["proba_1"] = probas[:, 1]
    grid["proba_2"] = probas[:, 2]

    # Score composite : probabilités ML + densité (pas le degré voisin = cible)
    risk_scores: list[float] = []
    for _, row in grid.iterrows():
        density_factor = min(float(row["density"]) / 8.0, 1.0)
        risk_scores.append(
            min(
                1.0,
                float(row["proba_1"]) * 0.45
                + float(row["proba_2"]) * 0.95
                + density_factor * 0.25,
            )
        )
    grid["risk_score"] = risk_scores
    grid["label"] = grid["prediction"].map(RISK_LABELS)
    return grid


def serialize_grid_points(grid_df: pd.DataFrame) -> list[dict[str, Any]]:
    cols = [
        "latitude_report",
        "longitude_report",
        "prediction",
        "confidence",
        "proba_0",
        "proba_1",
        "proba_2",
        "risk_score",
        "density",
        "nearest_neighbor_km",
        "mean_degree_danger",
        "label",
    ]
    present = [c for c in cols if c in grid_df.columns]
    return grid_df[present].to_dict(orient="records")


def _in_urban_kinshasa(lat: float, lon: float) -> bool:
    if not (
        KINSHASA_LAT_MIN <= lat <= KINSHASA_LAT_MAX
        and KINSHASA_LON_MIN <= lon <= KINSHASA_LON_MAX
    ):
        return False
    return is_prediction_land(lat, lon)


def _faible_point_pertinent(
    *,
    risk_score: float,
    density: float,
    confidence: float,
    mean_danger: float,
    lat: float,
    lon: float,
) -> bool:
    """
    Faible pertinent = zone documentée par des signalements, même si le ML hésite.
    Pas de cercle faible « isolé » sans historique local.
    """
    if not _in_urban_kinshasa(lat, lon) or density < 2:
        return False
    if density >= 3 and risk_score >= 0.30:
        return True
    if density >= 2 and mean_danger >= 0.5 and risk_score >= 0.28:
        return True
    if density >= 2 and confidence >= 0.48 and risk_score >= 0.34:
        return True
    return False


def _point_visible_on_map(point: dict[str, Any]) -> bool:
    """
    Cercles = vigilance utile : modéré/élevé cohérents, ou faible avec signalements terrain.
    """
    prediction = int(point.get("prediction", 0))
    risk_score = float(point.get("risk_score", 0))
    density = float(point.get("density", 0))
    confidence = float(point.get("confidence", 0))
    mean_danger = float(point.get("mean_degree_danger", 0))
    lat = float(point.get("latitude_report", 0))
    lon = float(point.get("longitude_report", 0))

    if prediction == 0:
        return _faible_point_pertinent(
            risk_score=risk_score,
            density=density,
            confidence=confidence,
            mean_danger=mean_danger,
            lat=lat,
            lon=lon,
        )

    if density >= 1:
        if not _in_urban_kinshasa(lat, lon):
            return False
        if prediction >= 2:
            return confidence >= 0.55 and risk_score >= 0.48
        return confidence >= 0.58 and risk_score >= 0.40

    if not _in_urban_kinshasa(lat, lon):
        return False
    if prediction >= 2 and confidence >= 0.75 and risk_score >= 0.85:
        return True
    if prediction >= 1 and confidence >= 0.9 and risk_score >= 0.5:
        return True
    return False


def filter_heatmap_points(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [p for p in points if _point_visible_on_map(p)]


def _risk_level_from_pct(pct_eleve: float, pct_modere: float, avg_risk: float) -> str:
    if pct_eleve >= 25 or avg_risk >= 0.65:
        return "eleve"
    if pct_modere >= 30 or pct_eleve >= 10 or avg_risk >= 0.4:
        return "modere"
    return "faible"


def build_kinshasa_sectors(
    grid_df: pd.DataFrame,
    reports_df: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    min_lon, min_lat = KINSHASA_BOUNDS["min_lon"], KINSHASA_BOUNDS["min_lat"]
    max_lon, max_lat = KINSHASA_BOUNDS["max_lon"], KINSHASA_BOUNDS["max_lat"]
    lon_step = (max_lon - min_lon) / SECTOR_COLS
    lat_step = (max_lat - min_lat) / SECTOR_ROWS

    sectors: list[dict[str, Any]] = []
    for row_idx in range(SECTOR_ROWS):
        for col_idx in range(SECTOR_COLS):
            s_min_lon = min_lon + col_idx * lon_step
            s_max_lon = min_lon + (col_idx + 1) * lon_step
            s_min_lat = min_lat + row_idx * lat_step
            s_max_lat = min_lat + (row_idx + 1) * lat_step

            is_last_row = row_idx == SECTOR_ROWS - 1
            is_last_col = col_idx == SECTOR_COLS - 1
            lon_mask = (
                grid_df["longitude_report"] <= s_max_lon
                if is_last_col
                else grid_df["longitude_report"] < s_max_lon
            )
            lat_mask = (
                grid_df["latitude_report"] <= s_max_lat
                if is_last_row
                else grid_df["latitude_report"] < s_max_lat
            )
            mask = (
                (grid_df["longitude_report"] >= s_min_lon)
                & lon_mask
                & (grid_df["latitude_report"] >= s_min_lat)
                & lat_mask
            )
            subset = grid_df[mask]
            if subset.empty:
                continue

            total = len(subset)
            grid_pct_faible = round((subset["prediction"] == 0).sum() / total * 100, 1)
            grid_pct_modere = round((subset["prediction"] == 1).sum() / total * 100, 1)
            grid_pct_eleve = round((subset["prediction"] == 2).sum() / total * 100, 1)
            avg_risk = round(float(subset["risk_score"].mean()), 3)
            avg_density = round(float(subset["density"].mean()), 2)

            observed = (
                observed_sector_stats(
                    reports_df,
                    min_lon=s_min_lon,
                    max_lon=s_max_lon,
                    min_lat=s_min_lat,
                    max_lat=s_max_lat,
                    include_max_boundary=is_last_row or is_last_col,
                )
                if reports_df is not None and len(reports_df)
                else None
            )

            if observed and observed["observed_report_count"] > 0:
                pct_faible = observed["pct_faible"]
                pct_modere = observed["pct_modere"]
                pct_eleve = observed["pct_eleve"]
                risk_level = _risk_level_from_pct(
                    pct_eleve,
                    pct_modere,
                    max(avg_risk, observed["avg_observed_degree"]),
                )
            else:
                pct_faible = grid_pct_faible
                pct_modere = grid_pct_modere
                pct_eleve = grid_pct_eleve
                risk_level = _risk_level_from_pct(pct_eleve, pct_modere, avg_risk)

            sectors.append(
                {
                    "sector_id": f"S_{row_idx}_{col_idx}",
                    "row": row_idx,
                    "col": col_idx,
                    "bounds": {
                        "min_lat": round(s_min_lat, 5),
                        "max_lat": round(s_max_lat, 5),
                        "min_lon": round(s_min_lon, 5),
                        "max_lon": round(s_max_lon, 5),
                    },
                    "polygon": [
                        [s_min_lon, s_min_lat],
                        [s_max_lon, s_min_lat],
                        [s_max_lon, s_max_lat],
                        [s_min_lon, s_max_lat],
                        [s_min_lon, s_min_lat],
                    ],
                    "pct_faible": pct_faible,
                    "pct_modere": pct_modere,
                    "pct_eleve": pct_eleve,
                    "grid_pct_faible": float(grid_pct_faible),
                    "grid_pct_modere": float(grid_pct_modere),
                    "grid_pct_eleve": float(grid_pct_eleve),
                    "observed_report_count": (
                        observed["observed_report_count"] if observed else 0
                    ),
                    "avg_risk_score": avg_risk,
                    "avg_density": avg_density,
                    "risk_level": risk_level,
                    "point_count": total,
                }
            )
    return sectors


def build_legend() -> dict[str, Any]:
    return {
        "title": "Carte de chaleur des risques — Kinshasa",
        "description": (
            "Le modèle prédit le niveau de danger (faible / modéré / élevé) à partir "
            "de la position, de l'heure, et surtout de la densité des signalements "
            "validés à proximité (~500 m)."
        ),
        "why_sparse": (
            "Les cercles affichent modéré/élevé confiants, ou faible seulement si "
            "plusieurs signalements validés à proximité (~500 m)."
        ),
        "colors": {
            "faible": {"hex": "#22c55e", "label": "Faible"},
            "modere": {"hex": "#eab308", "label": "Modéré"},
            "eleve": {"hex": "#ef4444", "label": "Élevé"},
        },
        "heatmap_scale": [
            "Bleu/vert : faible densité de risque",
            "Jaune/orange : vigilance",
            "Rouge : forte concentration de risque prédit",
        ],
        "sectors_note": (
            "Les pourcentages par secteur s'appuient sur les signalements validés "
            "présents dans la zone ; à défaut, sur la grille de prédiction ML."
        ),
    }
