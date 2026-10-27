"""Feature engineering géospatial — sans fuite de la cible (degré)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

from prediction_shared.labels import (
    DEGREE_LABEL_MAP,
    FEATURE_NAMES,
    KINSHASA_LAT_MAX,
    KINSHASA_LAT_MIN,
    KINSHASA_LON_MAX,
    KINSHASA_LON_MIN,
    RADIUS_KM,
)

# Centre approximatif Kinshasa (pour distance relative)
_CENTER_LAT = (KINSHASA_LAT_MIN + KINSHASA_LAT_MAX) / 2.0
_CENTER_LON = (KINSHASA_LON_MIN + KINSHASA_LON_MAX) / 2.0

# lat, lon, hour, day, density, nearest_neighbor_km — jamais le degré (cible)
RAW_FEATURE_COUNT = 6
EARTH_RADIUS_KM = 6371.0


def parse_hour_day(
    created_at: str | float | None,
    *,
    default_hour: int = 14,
    default_day: int = 2,
) -> tuple[int, int]:
    if created_at is None or (isinstance(created_at, float) and np.isnan(created_at)):
        return default_hour, default_day
    text = str(created_at).strip()
    if not text:
        return default_hour, default_day
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt.hour, dt.weekday()
        except ValueError:
            continue
    return default_hour, default_day


def build_raw_feature_matrix(
    df: pd.DataFrame,
    *,
    exclude_self: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Construit X brut (sans le degré des voisins) et y (cible).

    Variables spatiales :
    - density_500m : nombre de voisins (compte uniquement, pas leur gravité)
    - nearest_neighbor_km : distance au plus proche autre signalement
    """
    working = df.copy().reset_index(drop=True)
    working["degree_report"] = (
        working["degree_report"].map(DEGREE_LABEL_MAP).fillna(0).astype(int)
    )

    coords_rad = np.radians(working[["latitude_report", "longitude_report"]].to_numpy())
    tree = BallTree(coords_rad, metric="haversine")
    radius_rad = RADIUS_KM / EARTH_RADIUS_KM

    features: list[list[float]] = []
    labels: list[int] = []
    n = len(working)

    for idx, row in working.iterrows():
        point_rad = np.radians([[row["latitude_report"], row["longitude_report"]]])
        neighbors = tree.query_radius(point_rad, r=radius_rad)[0]
        if exclude_self:
            neighbors = neighbors[neighbors != idx]
        density = int(len(neighbors))

        # Distance au plus proche voisin (sans utiliser le degré)
        if n <= 1:
            nearest_km = RADIUS_KM
        else:
            k = min(2, n)
            dists, inds = tree.query(point_rad, k=k)
            # haversine BallTree renvoie des distances en radians
            dist_km = dists[0] * EARTH_RADIUS_KM
            if exclude_self and k >= 2 and inds[0][0] == idx:
                nearest_km = float(dist_km[1])
            else:
                nearest_km = float(dist_km[0]) if inds[0][0] != idx else (
                    float(dist_km[1]) if k >= 2 else RADIUS_KM
                )

        hour, day = parse_hour_day(row.get("created_at"))
        features.append(
            [
                float(row["latitude_report"]),
                float(row["longitude_report"]),
                float(hour),
                float(day),
                float(density),
                float(nearest_km),
            ]
        )
        labels.append(int(row["degree_report"]))

    return np.array(features, dtype=float), np.array(labels, dtype=int)


def engineer_feature_matrix(X_raw: np.ndarray) -> np.ndarray:
    """
    Enrichit les features brutes (après split).
    Entrée : (n, 6) = lat, lon, hour, day, density, nearest_neighbor_km
    Pas de variable dérivée du degré (cible).
    """
    if X_raw.ndim != 2 or X_raw.shape[1] < RAW_FEATURE_COUNT:
        raise ValueError(
            f"X_raw attendu (n, {RAW_FEATURE_COUNT}), reçu {getattr(X_raw, 'shape', None)}"
        )

    lat = X_raw[:, 0]
    lon = X_raw[:, 1]
    hour = X_raw[:, 2]
    day = X_raw[:, 3]
    dens = X_raw[:, 4]
    nearest_km = X_raw[:, 5]

    lat = np.nan_to_num(lat, nan=_CENTER_LAT)
    lon = np.nan_to_num(lon, nan=_CENTER_LON)
    hour = np.clip(np.nan_to_num(hour, nan=14.0), 0, 23)
    day = np.clip(np.nan_to_num(day, nan=2.0), 0, 6)
    dens = np.clip(np.nan_to_num(dens, nan=0.0), 0, None)
    nearest_km = np.clip(np.nan_to_num(nearest_km, nan=RADIUS_KM), 0, None)

    hour_rad = 2.0 * np.pi * hour / 24.0
    day_rad = 2.0 * np.pi * day / 7.0
    is_night = ((hour >= 22) | (hour <= 5)).astype(float)
    is_weekend = (day >= 5).astype(float)
    is_evening = ((hour >= 18) & (hour < 22)).astype(float)
    dens_log = np.log1p(dens)
    dens_sq = dens**2
    dist_center = np.sqrt((lat - _CENTER_LAT) ** 2 + (lon - _CENTER_LON) ** 2)
    # Proximité inverse (plus un voisin est proche, plus la valeur est haute) — sans label
    proximity = 1.0 / (1.0 + nearest_km)

    return np.column_stack(
        [
            lat,
            lon,
            hour,
            day,
            dens,
            nearest_km,
            np.sin(hour_rad),
            np.cos(hour_rad),
            np.sin(day_rad),
            np.cos(day_rad),
            is_night,
            is_weekend,
            is_evening,
            dens_log,
            dens_sq,
            dist_center,
            proximity,
        ]
    ).astype(float)


def build_feature_matrix(
    df: pd.DataFrame,
    *,
    exclude_self: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Pipeline complet : features brutes + engineering (après split)."""
    X_raw, y = build_raw_feature_matrix(df, exclude_self=exclude_self)
    return engineer_feature_matrix(X_raw), y


def feature_target_correlations(X: np.ndarray, y: np.ndarray) -> list[dict[str, Any]]:
    """Corrélations de Pearson feature ↔ label (calculées sur le train uniquement)."""
    rows: list[dict[str, Any]] = []
    if len(y) < 3:
        return rows
    y_f = y.astype(float)
    for i, name in enumerate(FEATURE_NAMES):
        if i >= X.shape[1]:
            break
        col = X[:, i]
        if np.std(col) < 1e-12 or np.std(y_f) < 1e-12:
            corr = 0.0
        else:
            corr = float(np.corrcoef(col, y_f)[0, 1])
            if np.isnan(corr):
                corr = 0.0
        rows.append(
            {
                "feature": name,
                "correlation": round(corr, 4),
                "abs_correlation": round(abs(corr), 4),
                "pertinent": abs(corr) >= 0.08,
            }
        )
    rows.sort(key=lambda r: -r["abs_correlation"])
    return rows


def build_inference_raw_row(
    latitude: float,
    longitude: float,
    reference_df: pd.DataFrame,
    *,
    created_at: str | None = None,
    hour: int | None = None,
    day_of_week: int | None = None,
) -> np.ndarray:
    """Une ligne brute (1, 6) pour l'inférence — sans degré voisin."""
    ref = reference_df.copy().reset_index(drop=True)
    if "degree_report" in ref.columns:
        # degree présent dans le CSV mais NON utilisé comme feature
        pass

    if len(ref) == 0:
        h, d = parse_hour_day(created_at) if hour is None else (hour, day_of_week or 2)
        return np.array([[latitude, longitude, float(h), float(d), 0.0, RADIUS_KM]])

    coords_rad = np.radians(ref[["latitude_report", "longitude_report"]].to_numpy())
    tree = BallTree(coords_rad, metric="haversine")
    radius_rad = RADIUS_KM / EARTH_RADIUS_KM
    point_rad = np.radians([[latitude, longitude]])
    neighbors = tree.query_radius(point_rad, r=radius_rad)[0]
    density = int(len(neighbors))

    dists, _ = tree.query(point_rad, k=1)
    nearest_km = float(dists[0][0] * EARTH_RADIUS_KM)

    if hour is None or day_of_week is None:
        parsed_h, parsed_d = parse_hour_day(created_at)
        hour = parsed_h if hour is None else hour
        day_of_week = parsed_d if day_of_week is None else day_of_week

    return np.array(
        [[latitude, longitude, float(hour), float(day_of_week), density, nearest_km]],
        dtype=float,
    )


def build_inference_features(
    latitude: float,
    longitude: float,
    reference_df: pd.DataFrame,
    *,
    created_at: str | None = None,
    hour: int | None = None,
    day_of_week: int | None = None,
) -> np.ndarray:
    """Features engineered pour un point unique."""
    raw = build_inference_raw_row(
        latitude,
        longitude,
        reference_df,
        created_at=created_at,
        hour=hour,
        day_of_week=day_of_week,
    )
    return engineer_feature_matrix(raw)
