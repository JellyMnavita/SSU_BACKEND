"""Proximité des signalements validés — pénalités trajet et stats secteurs."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

from prediction_shared.labels import RADIUS_KM

# Distances en km
REPORT_ON_POINT_KM = 0.05
REPORT_VERY_CLOSE_KM = 0.12
REPORT_NEAR_KM = 0.35
REPORT_ZONE_KM = RADIUS_KM


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _point_segment_distance_km(
    plat: float, plon: float, a: tuple[float, float], b: tuple[float, float]
) -> float:
    """Distance minimale point → segment (lat/lon), échantillonnage fin."""
    alat, alon = a
    blat, blon = b
    samples = max(2, int(_haversine_km(alat, alon, blat, blon) / 0.025) + 1)
    best = float("inf")
    for t in np.linspace(0, 1, samples):
        lat = alat + (blat - alat) * t
        lon = alon + (blon - alon) * t
        best = min(best, _haversine_km(plat, plon, lat, lon))
    return best


def min_distance_to_route_km(
    lat: float, lon: float, geometry: list[list[float]]
) -> float:
    if len(geometry) < 2:
        return float("inf")
    best = float("inf")
    for i in range(len(geometry) - 1):
        a = geometry[i]
        b = geometry[i + 1]
        if len(a) < 2 or len(b) < 2:
            continue
        lon_a, lat_a = float(a[0]), float(a[1])
        lon_b, lat_b = float(b[0]), float(b[1])
        best = min(
            best,
            _point_segment_distance_km(lat, lon, (lat_a, lon_a), (lat_b, lon_b)),
        )
    return best


def report_proximity_hazard(
    lat: float,
    lon: float,
    reports_df: pd.DataFrame,
    tree: BallTree,
) -> dict[str, Any]:
    """
    Score 0–1 basé sur les signalements validés réels (pas seulement le modèle ML).
    Passe sur un point signalé élevé → hazard ≈ 1.
    """
    point_rad = np.radians([[lat, lon]])
    radius_rad = REPORT_ZONE_KM / 6371.0
    indices = tree.query_radius(point_rad, r=radius_rad)[0]

    if len(indices) == 0:
        return {
            "hazard_score": 0.0,
            "nearest_report_km": None,
            "nearest_degree": None,
            "reports_in_zone": 0,
        }

    hazard = 0.0
    nearest_km = float("inf")
    nearest_degree = 0

    for idx in indices:
        row = reports_df.iloc[idx]
        rlat = float(row["latitude_report"])
        rlon = float(row["longitude_report"])
        degree = int(row["degree_report"])
        dist = _haversine_km(lat, lon, rlat, rlon)
        nearest_km = min(nearest_km, dist)
        if dist <= nearest_km + 1e-9:
            nearest_degree = degree

        severity = (degree + 1) / 3.0
        if dist <= REPORT_ON_POINT_KM:
            point_hazard = 0.92 + severity * 0.08
        elif dist <= REPORT_VERY_CLOSE_KM:
            point_hazard = 0.72 + severity * 0.18
        elif dist <= REPORT_NEAR_KM:
            point_hazard = 0.45 + severity * 0.25
        else:
            falloff = 1.0 - (dist - REPORT_NEAR_KM) / max(REPORT_ZONE_KM - REPORT_NEAR_KM, 0.01)
            point_hazard = max(0.0, falloff) * (0.25 + severity * 0.35)

        hazard = max(hazard, point_hazard)

    return {
        "hazard_score": round(min(1.0, hazard), 4),
        "nearest_report_km": round(nearest_km, 4) if nearest_km < float("inf") else None,
        "nearest_degree": nearest_degree,
        "reports_in_zone": int(len(indices)),
    }


def enrich_route_sample_points(
    geometry: list[list[float]],
    reports_df: pd.DataFrame,
    *,
    base_samples: list[tuple[float, float]],
    close_km: float = REPORT_VERY_CLOSE_KM,
) -> list[tuple[float, float]]:
    """Ajoute les signalements proches du tracé pour ne pas les « rater » à l'échantillonnage."""
    extra: list[tuple[float, float]] = []
    seen: set[tuple[float, float]] = set()

    for _, row in reports_df.iterrows():
        lat = float(row["latitude_report"])
        lon = float(row["longitude_report"])
        if min_distance_to_route_km(lat, lon, geometry) <= close_km:
            key = (round(lat, 5), round(lon, 5))
            if key not in seen:
                seen.add(key)
                extra.append((lat, lon))

    merged = list(base_samples)
    for point in extra:
        if point not in merged:
            merged.append(point)
    return merged


def observed_sector_stats(
    reports_df: pd.DataFrame,
    *,
    min_lon: float,
    max_lon: float,
    min_lat: float,
    max_lat: float,
    include_max_boundary: bool = False,
) -> dict[str, Any] | None:
    """Pourcentages basés sur les signalements validés dans le secteur."""
    lon_cmp = reports_df["longitude_report"] <= max_lon if include_max_boundary else reports_df["longitude_report"] < max_lon
    lat_cmp = reports_df["latitude_report"] <= max_lat if include_max_boundary else reports_df["latitude_report"] < max_lat
    mask = (
        (reports_df["longitude_report"] >= min_lon)
        & lon_cmp
        & (reports_df["latitude_report"] >= min_lat)
        & lat_cmp
    )
    subset = reports_df.loc[mask]
    if subset.empty:
        return None

    total = len(subset)
    counts = {0: 0, 1: 0, 2: 0}
    for degree in subset["degree_report"].astype(int):
        counts[int(degree)] = counts.get(int(degree), 0) + 1

    pct_faible = round(counts[0] / total * 100, 1)
    pct_modere = round(counts[1] / total * 100, 1)
    pct_eleve = round(counts[2] / total * 100, 1)
    avg_observed = round((counts[0] * 0 + counts[1] * 1 + counts[2] * 2) / total / 2, 3)

    return {
        "observed_report_count": total,
        "pct_faible": pct_faible,
        "pct_modere": pct_modere,
        "pct_eleve": pct_eleve,
        "avg_observed_degree": avg_observed,
    }
