"""Géolocalisation Kinshasa à partir du texte d'un article."""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from functools import lru_cache

import requests
from django.core.cache import cache

from locations.models import Commune, Quartier
from scrapping.services.sources import USER_AGENT

logger = logging.getLogger(__name__)

# Centre-ville Kinshasa (fallback ultime)
KINSHASA_CENTER = (-4.3217, 15.3125)

# Commune « Kinshasa » en base = zone administrative générique, pas la ville entière.
GENERIC_COMMUNE_NAMES = frozenset({"kinshasa"})

COMMUNE_CENTERS: dict[str, tuple[float, float]] = {
    "bandalungwa": (-4.345, 15.278),
    "barumbu": (-4.325, 15.305),
    "bumbu": (-4.358, 15.255),
    "gombe": (-4.305, 15.304),
    "kalamu": (-4.338, 15.292),
    "kasavubu": (-4.330, 15.288),
    "kimbanseke": (-4.385, 15.395),
    "kinshasa": (-4.322, 15.313),
    "kintambo": (-4.318, 15.278),
    "kisenso": (-4.405, 15.335),
    "lemba": (-4.395, 15.318),
    "limete": (-4.356, 15.313),
    "lingwala": (-4.318, 15.298),
    "makala": (-4.365, 15.278),
    # Maluku / Nsele : communes très étendues à l'est (Menkao, RN1, etc.)
    "maluku": (-4.260, 15.850),
    "masina": (-4.378, 15.365),
    "matete": (-4.368, 15.338),
    "mont ngafula": (-4.418, 15.245),
    "ndjili": (-4.408, 15.378),
    "ngaba": (-4.352, 15.268),
    "ngaliema": (-4.378, 15.248),
    "ngiri ngiri": (-4.348, 15.262),
    "nsele": (-4.285, 15.910),
    "selembao": (-4.372, 15.252),
}

# Quartiers fréquents dans la presse (si absents de la base ou sans polygone GPS).
QUARTIER_HINTS: dict[str, tuple[str, float, float]] = {
    "delvaux": ("Delvaux, Ngaliema, Kinshasa", -4.4012, 15.2568),
    "binza": ("Binza, Ngaliema, Kinshasa", -4.3880, 15.2420),
    "mont fleuri": ("Mont Fleuri, Ngaliema, Kinshasa", -4.3720, 15.2650),
    "victoire": ("Victoire, Ngaliema, Kinshasa", -4.3650, 15.2720),
    "upn": ("UPN, Ngaliema, Kinshasa", -4.3950, 15.2380),
    "joli parc": ("Joli Parc, Ngaliema, Kinshasa", -4.3840, 15.2510),
    "gombe": ("Gombe, Kinshasa", -4.305, 15.304),
    "kingabwa": ("Kingabwa, Limete, Kinshasa", -4.3480, 15.3280),
    "matete": ("Matete, Kinshasa", -4.368, 15.338),
    "masina": ("Masina, Kinshasa", -4.378, 15.365),
    "limete": ("Limete, Kinshasa", -4.356, 15.313),
    "kintambo": ("Kintambo, Kinshasa", -4.318, 15.278),
}

STRUCTURED_LOCATION_PATTERNS = [
    re.compile(
        r"quartier\s+([a-z0-9][a-z0-9\s\-']{1,40}?)\s*,\s*commune\s+(?:de\s+)?([a-z0-9][a-z0-9\s\-']{1,40})",
        re.IGNORECASE,
    ),
    re.compile(
        r"quartier\s+([a-z0-9][a-z0-9\s\-']{1,40}?)\s*,?\s*commune\s+(?:de\s+)?([a-z0-9][a-z0-9\s\-']{1,40})",
        re.IGNORECASE,
    ),
    re.compile(
        r"dans\s+le\s+quartier\s+([a-z0-9][a-z0-9\s\-']{1,40}?)(?:\s*,\s*commune\s+(?:de\s+)?([a-z0-9][a-z0-9\s\-']{1,40}))?",
        re.IGNORECASE,
    ),
    re.compile(
        r"commune\s+(?:de\s+)?([a-z0-9][a-z0-9\s\-']{1,40})",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bà\s+([a-z0-9][a-z0-9\s\-']{2,40})\b",
        re.IGNORECASE,
    ),
]


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


def _normalize(text: str) -> str:
    text = _strip_accents(text or "").lower()
    text = text.replace("'", "'").replace("-", " ")
    return re.sub(r"\s+", " ", text).strip()


def _commune_lookup_key(name: str) -> str:
    return _normalize(name).replace("-", " ")


def _needle_in_text(needle: str, normalized: str) -> bool:
    needle = _normalize(needle)
    if not needle or len(needle) < 3:
        return False
    pattern = rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])"
    return bool(re.search(pattern, normalized))


@lru_cache(maxsize=1)
def _place_index() -> list[tuple[str, str, str | None, bool]]:
    """(needle, label, quartier_id, is_quartier) triés du plus long au plus court."""
    entries: list[tuple[str, str, str | None, bool]] = []
    for q in Quartier.objects.select_related("commune").all():
        if _normalize(q.nom) in GENERIC_COMMUNE_NAMES:
            continue
        label = f"{q.nom}, {q.commune.nom}, Kinshasa"
        entries.append((_normalize(q.nom), label, str(q.pk), True))
        entries.append((_normalize(f"{q.nom} {q.commune.nom}"), label, str(q.pk), True))
    for c in Commune.objects.all():
        if _normalize(c.nom) in GENERIC_COMMUNE_NAMES:
            continue
        label = f"{c.nom}, Kinshasa"
        entries.append((_normalize(c.nom), label, None, False))
    for hint_key in sorted(QUARTIER_HINTS, key=len, reverse=True):
        label, _, _ = QUARTIER_HINTS[hint_key]
        entries.append((_normalize(hint_key), label, None, True))
    entries.sort(key=lambda x: len(x[0]), reverse=True)
    return entries


def _centroid_from_limites(limites_gps: str) -> tuple[float, float] | None:
    try:
        data = json.loads(limites_gps or "[]")
    except json.JSONDecodeError:
        return None
    if not data:
        return None
    lats, lons = [], []
    for ring in data if isinstance(data[0], list) else [data]:
        for pt in ring:
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                lons.append(float(pt[0]))
                lats.append(float(pt[1]))
    if not lats:
        return None
    return (sum(lats) / len(lats), sum(lons) / len(lons))


def _nominatim(query: str) -> tuple[float, float] | None:
    cache_key = f"news_geo:{query.lower()}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": query,
                "format": "json",
                "limit": 1,
                "countrycodes": "cd",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=12,
        )
        resp.raise_for_status()
        results = resp.json()
        if not results:
            return None
        lat = float(results[0]["lat"])
        lon = float(results[0]["lon"])
        coords = (lat, lon)
        cache.set(cache_key, coords, 60 * 60 * 24)
        return coords
    except Exception as exc:
        logger.warning("Nominatim échec pour %r: %s", query, exc)
        return None


def _coords_for_commune(commune_name: str) -> tuple[float, float] | None:
    key = _commune_lookup_key(commune_name)
    if key in COMMUNE_CENTERS:
        return COMMUNE_CENTERS[key]
    return _nominatim(f"{commune_name}, Kinshasa, République démocratique du Congo")


def _coords_for_label(label: str, is_quartier: bool, quartier_id: str | None) -> tuple[float, float]:
    if quartier_id:
        quartier = Quartier.objects.filter(pk=quartier_id).first()
        if quartier and quartier.limites_gps:
            centroid = _centroid_from_limites(quartier.limites_gps)
            if centroid:
                return centroid

    hint_key = _normalize(label.split(",")[0])
    if hint_key in QUARTIER_HINTS:
        return QUARTIER_HINTS[hint_key][1], QUARTIER_HINTS[hint_key][2]

    parts = [p.strip() for p in label.split(",")]
    commune_name = parts[1] if is_quartier and len(parts) >= 2 else parts[0]
    coords = _coords_for_commune(commune_name)
    if coords:
        return coords

    geo = _nominatim(f"{label}, République démocratique du Congo")
    if geo:
        return geo
    return KINSHASA_CENTER


def _match_from_structured_patterns(normalized: str) -> dict | None:
    for pattern in STRUCTURED_LOCATION_PATTERNS:
        match = pattern.search(normalized)
        if not match:
            continue
        groups = [g.strip() for g in match.groups() if g]
        if not groups:
            continue

        if len(groups) >= 2:
            quartier_name, commune_name = groups[0], groups[1]
            q_key = _normalize(quartier_name)
            c_key = _normalize(commune_name)
            if q_key in QUARTIER_HINTS:
                label, lat, lon = QUARTIER_HINTS[q_key]
                return {
                    "latitude": lat,
                    "longitude": lon,
                    "location": f"{label}, RDC",
                    "quartier": _find_quartier_in_db(quartier_name, commune_name),
                    "estimated": True,
                }
            commune = Commune.objects.filter(nom__iexact=commune_name.strip()).first()
            if commune:
                lat, lon = _coords_for_commune(commune.nom) or KINSHASA_CENTER
                label = f"{quartier_name.title()}, {commune.nom}, Kinshasa"
                return {
                    "latitude": lat,
                    "longitude": lon,
                    "location": f"{label}, RDC",
                    "quartier": _find_quartier_in_db(quartier_name, commune.nom),
                    "estimated": True,
                }

        place = groups[0]
        p_key = _normalize(place)
        if p_key in QUARTIER_HINTS:
            label, lat, lon = QUARTIER_HINTS[p_key]
            return {
                "latitude": lat,
                "longitude": lon,
                "location": f"{label}, RDC",
                "quartier": None,
                "estimated": True,
            }
        commune = Commune.objects.filter(nom__iexact=place.strip()).first()
        if commune and _normalize(commune.nom) not in GENERIC_COMMUNE_NAMES:
            lat, lon = _coords_for_commune(commune.nom) or KINSHASA_CENTER
            return {
                "latitude": lat,
                "longitude": lon,
                "location": f"{commune.nom}, Kinshasa, RDC",
                "quartier": None,
                "estimated": True,
            }
    return None


def _find_quartier_in_db(quartier_name: str, commune_name: str) -> Quartier | None:
    commune = Commune.objects.filter(nom__iexact=commune_name.strip()).first()
    if not commune:
        return None
    return Quartier.objects.filter(commune=commune, nom__iexact=quartier_name.strip()).first()


def _match_from_place_index(normalized: str) -> dict | None:
    candidates: list[tuple[int, str, str, str | None, bool]] = []
    for needle, label, qid, is_quartier in _place_index():
        if not _needle_in_text(needle, normalized):
            continue
        priority = len(needle)
        if is_quartier:
            priority += 50
        candidates.append((priority, needle, label, qid, is_quartier))

    if not candidates:
        return None

    _, _, label, qid, is_quartier = max(candidates, key=lambda item: item[0])
    lat, lon = _coords_for_label(label, is_quartier, qid)
    quartier = Quartier.objects.filter(pk=qid).first() if qid else None
    return {
        "latitude": lat,
        "longitude": lon,
        "location": f"{label}, RDC",
        "quartier": quartier,
        "estimated": quartier is None,
    }


def geocode_kinshasa(text: str) -> dict | None:
    """
    Retourne latitude, longitude, location, quartier_id ou None si hors Kinshasa.
    """
    normalized = _normalize(text)
    places = _place_index()
    has_known_place = any(_needle_in_text(needle, normalized) for needle, _, _, _ in places)
    if "kinshasa" not in normalized and not has_known_place:
        return None

    structured = _match_from_structured_patterns(normalized)
    if structured:
        return structured

    indexed = _match_from_place_index(normalized)
    if indexed:
        return indexed

    if "kinshasa" in normalized:
        lat, lon = _nominatim("Kinshasa, République démocratique du Congo") or KINSHASA_CENTER
        return {
            "latitude": lat,
            "longitude": lon,
            "location": "Kinshasa, RDC",
            "quartier": None,
            "estimated": True,
        }

    return None


def clear_place_index_cache() -> None:
    _place_index.cache_clear()
