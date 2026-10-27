"""Masque terrestre Kinshasa — exclut le fleuve Congo / Pool Malebo des prédictions."""

from __future__ import annotations

# Bboxes (min_lon, min_lat, max_lon, max_lat) — eau du fleuve / pool
WATER_EXCLUSION_BOXES: list[tuple[float, float, float, float]] = [
    # Pool Malebo (entre rives Kinshasa est et Brazzaville)
    (15.180, -4.440, 15.278, -4.175),
    # Chenal nord (Lingwala / fleuve)
    (15.255, -4.200, 15.302, -4.070),
    # Bras sud avant le pool (Maluku / confluence)
    (15.305, -4.530, 15.390, -4.438),
]


def is_on_water(lat: float, lon: float) -> bool:
    """True si le point est dans une zone d'eau connue (fleuve Congo à Kinshasa)."""
    for min_lon, min_lat, max_lon, max_lat in WATER_EXCLUSION_BOXES:
        if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
            return True
    return False


def is_prediction_land(lat: float, lon: float) -> bool:
    """Point exploitable pour afficher une prédiction sur la carte."""
    return not is_on_water(lat, lon)
