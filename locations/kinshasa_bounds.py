"""Zone géographique autorisée — Kinshasa (contour OSM + bbox dérivée)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from rest_framework.exceptions import ValidationError
from shapely.geometry import Point, shape

_BOUNDARY_PATH = Path(__file__).resolve().parent / "data" / "kinshasa-boundary.geojson"

KINSHASA_GEO_ERROR = (
    "Les signalements et alertes ne sont autorisés qu'à Kinshasa (RDC)."
)


@lru_cache(maxsize=1)
def _kinshasa_geometry():
    payload = json.loads(_BOUNDARY_PATH.read_text(encoding="utf-8"))
    if payload.get("type") == "Feature":
        return shape(payload["geometry"])
    if payload.get("type") == "FeatureCollection":
        from shapely.ops import unary_union

        return unary_union([shape(f["geometry"]) for f in payload["features"]])
    return shape(payload)


@lru_cache(maxsize=1)
def _kinshasa_bounds_tuple() -> tuple[float, float, float, float]:
    min_lon, min_lat, max_lon, max_lat = _kinshasa_geometry().bounds
    return float(min_lon), float(min_lat), float(max_lon), float(max_lat)


def get_kinshasa_bounds() -> dict[str, float]:
    min_lon, min_lat, max_lon, max_lat = _kinshasa_bounds_tuple()
    return {
        "min_lat": min_lat,
        "max_lat": max_lat,
        "min_lon": min_lon,
        "max_lon": max_lon,
    }


# Bbox englobante du contour administratif (province de Kinshasa, OSM)
KINSHASA_BOUNDS = get_kinshasa_bounds()


def is_within_kinshasa_bounds(latitude: float, longitude: float) -> bool:
    return _kinshasa_geometry().contains(Point(longitude, latitude))


def assert_kinshasa_coordinates(latitude: float, longitude: float) -> None:
    if not is_within_kinshasa_bounds(latitude, longitude):
        raise ValidationError(KINSHASA_GEO_ERROR)
