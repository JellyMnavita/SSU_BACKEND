"""Libellés et constantes — prédiction de degré de danger."""

from __future__ import annotations

DEGREE_LABEL_MAP: dict[str, int] = {
    "faible": 0,
    "modéré": 1,
    "modere": 1,
    "élevé": 2,
    "eleve": 2,
}

CLASS_NAMES: list[str] = ["faible", "modere", "eleve"]
CLASS_NAMES_FR: list[str] = ["Faible", "Modéré", "Élevé"]
RISK_LABELS: dict[int, str] = {0: "faible", 1: "modere", 2: "eleve"}

FEATURE_NAMES: list[str] = [
    "latitude",
    "longitude",
    "hour",
    "day_of_week",
    "density_500m",
    "nearest_neighbor_km",
    # Engineering (après split) — aucune dérivée du degré (cible)
    "hour_sin",
    "hour_cos",
    "day_sin",
    "day_cos",
    "is_night",
    "is_weekend",
    "is_evening_peak",
    "density_log",
    "density_sq",
    "dist_from_city_center",
    "neighbor_proximity",
]

FEATURE_LABELS_FR: dict[str, str] = {
    "latitude": "Latitude",
    "longitude": "Longitude",
    "hour": "Heure (0–23)",
    "day_of_week": "Jour de la semaine (0=lundi)",
    "density_500m": "Densité de signalements (rayon 500 m, comptage seul)",
    "nearest_neighbor_km": "Distance au plus proche signalement (km)",
    "hour_sin": "Heure (sinus — cycle 24 h)",
    "hour_cos": "Heure (cosinus — cycle 24 h)",
    "day_sin": "Jour (sinus — cycle 7 j)",
    "day_cos": "Jour (cosinus — cycle 7 j)",
    "is_night": "Nuit (22 h–5 h)",
    "is_weekend": "Week-end",
    "is_evening_peak": "Soirée (18 h–22 h)",
    "density_log": "Densité (log)",
    "density_sq": "Densité au carré",
    "dist_from_city_center": "Distance au centre de Kinshasa",
    "neighbor_proximity": "Proximité du voisin le plus proche (1/(1+km))",
}

# Explications admin : création + pertinence (sans jargon inutile)
FEATURE_DETAILS_FR: dict[str, dict[str, str]] = {
    "latitude": {
        "type": "brute",
        "creation": "Prise directement de la position GPS du signalement (latitude).",
        "pertinence": "La criminalité n’est pas uniforme : certains axes et quartiers de Kinshasa sont plus exposés. La latitude aide le modèle à situer le point sur la carte.",
    },
    "longitude": {
        "type": "brute",
        "creation": "Prise directement de la position GPS du signalement (longitude).",
        "pertinence": "Associée à la latitude, elle localise l’incident est–ouest. Deux points proches partagent souvent un même contexte urbain.",
    },
    "hour": {
        "type": "brute",
        "creation": "Heure extraite de la date/heure du signalement (0 à 23).",
        "pertinence": "Les risques changent selon le moment de la journée (matin calme vs nuit plus exposée). L’heure est une information temporelle classique.",
    },
    "day_of_week": {
        "type": "brute",
        "creation": "Jour de la semaine dérivé de la date (0 = lundi … 6 = dimanche).",
        "pertinence": "Les rituels urbains diffèrent en semaine et le week-end (marchés, sorties, circulation). Cela influence quand les incidents se concentrent.",
    },
    "density_500m": {
        "type": "brute",
        "creation": "Nombre de signalements validés dans un rayon de 500 m autour du point (comptage uniquement, sans leur gravité).",
        "pertinence": "Une zone déjà très signalée est souvent plus sensible. On compte les voisins, on n’utilise pas leur degré : le degré est la cible à prédire, pas une entrée.",
    },
    "nearest_neighbor_km": {
        "type": "brute",
        "creation": "Distance (km) jusqu’au signalement validé le plus proche, calculée sur la sphère (formule haversine).",
        "pertinence": "Un incident isolé n’a pas le même sens qu’un cluster. La distance au voisin le plus proche mesure l’isolement spatial sans réutiliser la gravité.",
    },
    "hour_sin": {
        "type": "ingénierie",
        "creation": "sin(2π × heure / 24). Transforme l’heure en signal cyclique.",
        "pertinence": "À minuit, 23 h et 0 h sont proches dans la réalité ; une heure « plate » 0–23 les sépare artificiellement. Le sinus corrige ce faux saut.",
    },
    "hour_cos": {
        "type": "ingénierie",
        "creation": "cos(2π × heure / 24), complément du sinus horaire.",
        "pertinence": "Avec hour_sin, le couple (sin, cos) représente correctement le cycle 24 h pour le modèle.",
    },
    "day_sin": {
        "type": "ingénierie",
        "creation": "sin(2π × jour / 7).",
        "pertinence": "Idem pour la semaine : dimanche et lundi se suivent. Le cycle sinusoïdal évite de traiter 0 et 6 comme opposés.",
    },
    "day_cos": {
        "type": "ingénierie",
        "creation": "cos(2π × jour / 7).",
        "pertinence": "Complète day_sin pour encoder le rythme hebdomadaire sans rupture artificielle.",
    },
    "is_night": {
        "type": "ingénierie",
        "creation": "Indicateur 1 si l’heure est entre 22 h et 5 h inclus, sinon 0.",
        "pertinence": "La nuit réduit la surveillance naturelle et augmente certains risques (agressions, vols). Un drapeau binaire aide le modèle à capter ce régime.",
    },
    "is_weekend": {
        "type": "ingénierie",
        "creation": "Indicateur 1 si samedi ou dimanche (jour ≥ 5), sinon 0.",
        "pertinence": "Les flux et l’occupation de l’espace public changent le week-end ; la sécurité perçue aussi.",
    },
    "is_evening_peak": {
        "type": "ingénierie",
        "creation": "Indicateur 1 si l’heure est entre 18 h et 22 h (exclu), sinon 0.",
        "pertinence": "Créneau de déplacements intensifs (retour travail/école) : affluence et opportunités d’incidents plus élevées.",
    },
    "density_log": {
        "type": "ingénierie",
        "creation": "log(1 + densité). Compressée pour les fortes densités.",
        "pertinence": "Passer de 1 à 2 voisins n’est pas la même chose que de 20 à 21. Le log adoucit les zones très denses pour stabiliser l’apprentissage.",
    },
    "density_sq": {
        "type": "ingénierie",
        "creation": "Densité au carré (densité²).",
        "pertinence": "Renforce l’effet des zones vraiment saturées en signalements, où le risque collectif peut monter non linéairement.",
    },
    "dist_from_city_center": {
        "type": "ingénierie",
        "creation": "Distance euclidienne (en degrés) au centroid approximatif de Kinshasa.",
        "pertinence": "Centre-ville, couronnes et périphérie n’ont pas le même profil. Cette variable résume une position « relative » simple sans réutiliser la cible.",
    },
    "neighbor_proximity": {
        "type": "ingénierie",
        "creation": "1 / (1 + distance_km au voisin le plus proche).",
        "pertinence": "Plus le voisin est proche, plus la valeur est haute. C’est l’inverse utile de la distance : le modèle voit directement « proximité », toujours sans le degré.",
    },
}


def feature_catalog_for_admin() -> list[dict[str, str]]:
    """Catalogue complet des variables pour l’UI admin."""
    rows: list[dict[str, str]] = []
    for name in FEATURE_NAMES:
        detail = FEATURE_DETAILS_FR.get(name, {})
        rows.append(
            {
                "code": name,
                "libelle": FEATURE_LABELS_FR.get(name, name),
                "type": detail.get("type", "autre"),
                "creation": detail.get("creation", ""),
                "pertinence": detail.get("pertinence", ""),
            }
        )
    return rows


RADIUS_KM = 0.5

# Bbox approximative Kinshasa (filtrage outliers géographiques)
KINSHASA_LAT_MIN = -4.55
KINSHASA_LAT_MAX = -4.05
KINSHASA_LON_MIN = 14.95
KINSHASA_LON_MAX = 15.55
