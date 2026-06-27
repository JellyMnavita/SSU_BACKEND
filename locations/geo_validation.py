"""Validation géographique avancée — fleuve, eau et cohérence lieu ↔ GPS."""

from __future__ import annotations

import math
import re
import unicodedata
from functools import lru_cache

from rest_framework.exceptions import ValidationError
from shapely.geometry import Point, Polygon

from locations.kinshasa_bounds import assert_kinshasa_coordinates, is_within_kinshasa_bounds
from scrapping.services.geocoder import COMMUNE_CENTERS, QUARTIER_HINTS, _centroid_from_limites

WATER_ZONE_ERROR = (
    "Les coordonnées pointent vers le fleuve Congo ou une zone d'eau — "
    "signalement non accepté."
)
INCONSISTENT_LOCATION_ERROR = (
    "Les coordonnées GPS ne correspondent pas au lieu indiqué dans Kinshasa. "
    "Vérifiez la position sur la carte."
)

# Corridor étroit du fleuve Congo (ouest de Kinshasa uniquement).
# L'ancien polygone était trop large à l'est et marquait Selembao / Mont Ngafula à tort.
_CONGO_RIVER_POLYGON = Polygon(
    [
        (15.215, -4.480),
        (15.245, -4.480),
        (15.248, -4.400),
        (15.250, -4.320),
        (15.248, -4.240),
        (15.242, -4.170),
        (15.228, -4.150),
        (15.215, -4.150),
        (15.215, -4.480),
    ]
)

# Extrême sud-ouest (eau profonde) — ne couvre pas les communes côtières habitées.
_POOL_MALEBO_POLYGON = Polygon(
    [
        (15.175, -4.520),
        (15.220, -4.520),
        (15.225, -4.485),
        (15.215, -4.470),
        (15.175, -4.470),
        (15.175, -4.520),
    ]
)

COMMUNE_MAX_DISTANCE_KM = 25.0
# Communes rurales / très étendues à l'est de Kinshasa
LARGE_COMMUNE_MAX_DISTANCE_KM = 55.0
LARGE_COMMUNE_KEYS = frozenset({"maluku", "nsele"})
QUARTIER_MAX_DISTANCE_KM = 6.0
GENERIC_LOCATION_RE = re.compile(
    r"^(kinshasa|rdc|republique democratique du congo|ville de kinshasa)\b",
    re.IGNORECASE,
)
COORDS_LOCATION_RE = re.compile(
    r"^kinshasa\s*\(\s*-?\d",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text or "")
    stripped = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", stripped.lower()).strip()


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius_km * math.asin(min(1.0, math.sqrt(a)))


def is_on_water_zone(latitude: float, longitude: float) -> bool:
    point = Point(longitude, latitude)
    return _CONGO_RIVER_POLYGON.contains(point) or _POOL_MALEBO_POLYGON.contains(point)


def assert_not_on_water(latitude: float, longitude: float) -> None:
    if is_on_water_zone(latitude, longitude):
        raise ValidationError(WATER_ZONE_ERROR)


@lru_cache(maxsize=1)
def _quartier_centroids() -> dict[str, tuple[float, float]]:
    from locations.models import Quartier

    centroids: dict[str, tuple[float, float]] = {}
    for quartier in Quartier.objects.select_related("commune").iterator():
        centroid = _centroid_from_limites(quartier.limites_gps)
        if centroid:
            centroids[_normalize(quartier.nom)] = centroid
            centroids[_normalize(f"{quartier.nom} {quartier.commune.nom}")] = centroid
    for hint_key, (_, lat, lon) in QUARTIER_HINTS.items():
        centroids[_normalize(hint_key)] = (lat, lon)
    return centroids


def _find_commune_in_text(
    location: str,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
) -> str | None:
    normalized = _normalize(location)
    matches: list[str] = []
    for commune_key in COMMUNE_CENTERS:
        pattern = rf"(?<![a-z0-9]){re.escape(commune_key)}(?![a-z0-9])"
        if re.search(pattern, normalized):
            matches.append(commune_key)
    if not matches:
        return None
    if len(matches) == 1 or latitude is None or longitude is None:
        return matches[0]
    return min(
        matches,
        key=lambda key: haversine_km(
            latitude, longitude, COMMUNE_CENTERS[key][0], COMMUNE_CENTERS[key][1]
        ),
    )


def _find_quartier_in_text(location: str) -> str | None:
    normalized = _normalize(location)
    for quartier_key in sorted(_quartier_centroids(), key=len, reverse=True):
        if len(quartier_key) < 4:
            continue
        pattern = rf"(?<![a-z0-9]){re.escape(quartier_key)}(?![a-z0-9])"
        if re.search(pattern, normalized):
            return quartier_key
    return None


def location_coordinate_mismatch_km(
    latitude: float,
    longitude: float,
    *,
    location: str | None = None,
    quartier=None,
) -> float | None:
    """
    Distance (km) entre le GPS et l'ancre déduite du lieu.
    Retourne None si aucune ancre fiable n'est disponible.
    """
    anchor: tuple[float, float] | None = None

    if quartier is not None:
        centroid = _centroid_from_limites(getattr(quartier, "limites_gps", "") or "")
        if centroid:
            anchor = centroid
        else:
            commune_key = _normalize(getattr(quartier.commune, "nom", ""))
            anchor = COMMUNE_CENTERS.get(commune_key)

    if anchor is None and location:
        if GENERIC_LOCATION_RE.match(location.strip()) or COORDS_LOCATION_RE.match(
            location.strip()
        ):
            return None
        quartier_key = _find_quartier_in_text(location)
        if quartier_key:
            anchor = _quartier_centroids().get(quartier_key)
        if anchor is None:
            commune_key = _find_commune_in_text(
                location, latitude=latitude, longitude=longitude
            )
            if commune_key:
                anchor = COMMUNE_CENTERS.get(commune_key)

    if anchor is None:
        return None

    return haversine_km(latitude, longitude, anchor[0], anchor[1])


def assert_location_coordinate_consistency(
    latitude: float,
    longitude: float,
    *,
    location: str | None = None,
) -> None:
    """Cohérence GPS ↔ champ location du signalement (pas le domicile citoyen)."""
    mismatch_km = location_coordinate_mismatch_km(
        latitude,
        longitude,
        location=location,
    )
    if mismatch_km is None:
        return

    max_km = COMMUNE_MAX_DISTANCE_KM
    if location:
        quartier_key = _find_quartier_in_text(location)
        commune_key = _find_commune_in_text(
            location, latitude=latitude, longitude=longitude
        )
        if quartier_key is None and commune_key:
            max_km = (
                LARGE_COMMUNE_MAX_DISTANCE_KM
                if commune_key in LARGE_COMMUNE_KEYS
                else COMMUNE_MAX_DISTANCE_KM
            )
        elif quartier_key:
            max_km = QUARTIER_MAX_DISTANCE_KM

    if mismatch_km > max_km:
        raise ValidationError(INCONSISTENT_LOCATION_ERROR)


def assert_report_coordinates(
    latitude: float,
    longitude: float,
    *,
    location: str | None = None,
) -> None:
    """Kinshasa + hors eau + cohérence texte lieu/GPS (champ location uniquement)."""
    assert_kinshasa_coordinates(latitude, longitude)
    assert_not_on_water(latitude, longitude)
    assert_location_coordinate_consistency(
        latitude,
        longitude,
        location=location,
    )


def coordinate_quality_issue(
    latitude: float | None,
    longitude: float | None,
    *,
    location: str | None = None,
    quartier=None,
) -> str | None:
    """Raison textuelle pour nettoyage batch (sans lever d'exception)."""
    if latitude is None or longitude is None:
        return "coordonnées manquantes"
    if not is_within_kinshasa_bounds(latitude, longitude):
        return "hors Kinshasa"
    if is_on_water_zone(latitude, longitude):
        return "sur le fleuve ou zone d'eau"
    mismatch_km = location_coordinate_mismatch_km(
        latitude,
        longitude,
        location=location,
        quartier=quartier,
    )
    if mismatch_km is None:
        return None
    max_km = QUARTIER_MAX_DISTANCE_KM
    if quartier is None and location and not COORDS_LOCATION_RE.match(location.strip()):
        commune_key = _find_commune_in_text(
            location, latitude=latitude, longitude=longitude
        )
        if commune_key and _find_quartier_in_text(location) is None:
            max_km = (
                LARGE_COMMUNE_MAX_DISTANCE_KM
                if commune_key in LARGE_COMMUNE_KEYS
                else COMMUNE_MAX_DISTANCE_KM
            )
    if mismatch_km > max_km:
        return f"lieu incohérent ({mismatch_km:.1f} km d'écart)"
    return None


def random_point_near_commune(rng, commune_key: str) -> tuple[float, float]:
    base_lat, base_lon = COMMUNE_CENTERS[commune_key]
    for _ in range(40):
        lat = base_lat + rng.uniform(-0.018, 0.018)
        lon = base_lon + rng.uniform(-0.018, 0.018)
        if is_within_kinshasa_bounds(lat, lon) and not is_on_water_zone(lat, lon):
            return lat, lon
    return random_land_point_in_kinshasa(rng)


def random_land_point_in_kinshasa(rng, max_attempts: int = 500) -> tuple[float, float]:
    """Point aléatoire sur terre ferme à Kinshasa (rejection sampling)."""
    from locations.kinshasa_bounds import get_kinshasa_bounds

    bounds = get_kinshasa_bounds()
    for _ in range(max_attempts):
        lat = rng.uniform(bounds["min_lat"], bounds["max_lat"])
        lon = rng.uniform(bounds["min_lon"], bounds["max_lon"])
        if is_within_kinshasa_bounds(lat, lon) and not is_on_water_zone(lat, lon):
            return lat, lon
    raise RuntimeError("Impossible de tirer un point terrestre à Kinshasa.")
