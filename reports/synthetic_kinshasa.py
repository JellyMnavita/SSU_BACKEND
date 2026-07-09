"""
Génération de signalements synthétiques réalistes pour Kinshasa.

Méthodes statistiques utilisées :
- Tirage pondéré des communes (prior régional inspiré presse / rapports locaux)
- Degré F/M/E conditionnel au type d'incident (table de probabilités)
- Heure et jour de semaine : bootstrap sur CSV réel si disponible, sinon loi mixte
  (pics soirée 18h–23h, week-end)
- Coordonnées : jitter gaussien autour du centroïde commune + rejet eau/hors bbox
- Déduplication : empreinte (description normalisée + GPS arrondi) + distance minimale
- Variation textuelle : grammaire de templates (pas une liste fixe de 10 phrases)
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from locations.geo_validation import is_on_water_zone, random_point_near_commune
from locations.kinshasa_bounds import is_within_kinshasa_bounds
from scrapping.services.geocoder import COMMUNE_CENTERS, QUARTIER_HINTS

# Poids relatifs d'incidence par commune (presse 2024–2025 : kuluna, cambriolages, braquages)
COMMUNE_INCIDENCE_WEIGHTS: dict[str, float] = {
    "selembao": 1.35,
    "matete": 1.30,
    "bumbu": 1.28,
    "masina": 1.25,
    "kisenso": 1.22,
    "ngaba": 1.20,
    "makala": 1.18,
    "ndjili": 1.18,
    "kimbanseke": 1.15,
    "mont ngafula": 1.15,
    "ngiri ngiri": 1.12,
    "limete": 1.10,
    "lemba": 1.08,
    "kalamu": 1.05,
    "bandalungwa": 1.05,
    "kintambo": 1.00,
    "lingwala": 1.00,
    "kasavubu": 0.95,
    "ngaliema": 0.90,
    "barumbu": 0.85,
    "maluku": 0.70,
    "nsele": 0.65,
}

# Quartiers cités dans la presse locale (en plus des hints géocodeur)
COMMUNE_QUARTIERS: dict[str, list[str]] = {
    "bumbu": ["Dipiya", "Matadi", "Mbandaka", "Mfimi", "Ntomba", "Libération"],
    "selembao": ["Molende", "Bikinda", "Mbanza Ngungu", "Kimbwala"],
    "matete": ["Ngilima", "Kin Marché", "Salongo", "Sans Fil"],
    "ngiri ngiri": ["Monkoto", "Shaba", "Matadi", "Kalamu"],
    "mont ngafula": ["CPA Mushi", "Mbudi", "Makala", "Plateau"],
    "masina": ["Pilote", "Sans Fil", "Ebombé", "Mobutu"],
    "limete": ["Kingabwa", "Righini", "Salongo", "Livulu"],
    "kisenso": ["Lemba", "Matete", "Kinsuka"],
    "ndjili": ["Ndjili Sif", "Mikondo", "Kinkole"],
    "kimbanseke": ["Kimbanseke", "Mokali"],
    "kalamu": ["Matonge", "Kalamu", "Assossa"],
    "ngaliema": ["Binza", "Delvaux", "Mont Fleuri", "UPN", "Joli Parc"],
    "gombe": ["Centre-ville", "Gombe", "N°1"],
    "lingwala": ["Lingwala", "Ngiri-Ngiri", "Bandal"],
    "makala": ["Makala", "Camp Luka", "Kasavubu"],
    "lemba": ["Lemba", "Righini", "Matete"],
    "bandalungwa": ["Bandal", "Kasavubu"],
    "kintambo": ["Kintambo", "Victoire"],
    "kasavubu": ["Kasavubu", "Kalamu"],
    "barumbu": ["Barumbu", "Gombe"],
    "ngaba": ["Ngaba", "Petit Pont"],
    "kinshasa": ["Gombe", "Kinshasa"],
    "maluku": ["Menkao", "Kinkole"],
    "nsele": ["Nsele", "Kinkole"],
}

TIME_OPENERS = [
    "Ce {jour} vers {heure}h",
    "Hier {periode}, aux environs de {heure}h",
    "Témoin oculaire : vers {heure}h, {periode}",
    "Des riverains signalent {que_periode}, vers {heure}h",
    "Alerte reçue {jour} à {heure}h{minutes:02d}",
    "Plusieurs habitants indiquent {que_periode}",
]

WEEKDAYS_FR = [
    "lundi",
    "mardi",
    "mercredi",
    "jeudi",
    "vendredi",
    "samedi",
    "dimanche",
]

PERIODS = ["le matin", "l'après-midi", "en soirée", "dans la nuit", "tôt le matin"]


def _period_for_hour(hour: int) -> str:
    """Période cohérente avec l'heure numérique (évite « vers 15h en soirée »)."""
    if 5 <= hour <= 8:
        return "tôt le matin"
    if 9 <= hour <= 11:
        return "le matin"
    if 12 <= hour <= 17:
        return "l'après-midi"
    if 18 <= hour <= 22:
        return "en soirée"
    return "dans la nuit"


def _que_periode(periode: str) -> str:
    """Accord grammatical : qu'en soirée / que le matin / que l'après-midi."""
    if periode.startswith("en "):
        return f"qu'{periode}"
    return f"que {periode}"


@dataclass(frozen=True)
class IncidentScenario:
    key: str
    templates: tuple[str, ...]
    degree_weights: tuple[tuple[str, float], ...]  # F, M, E
    hour_bias: tuple[int, ...]  # heures privilégiées


INCIDENT_SCENARIOS: tuple[IncidentScenario, ...] = (
    IncidentScenario(
        "kuluna_machette",
        (
            "un groupe de jeunes armés de machettes a intimidé les passants près de {lieu}.",
            "des individus qualifiés de kuluna ont brisé des pare-brises pour voler des effets dans des véhicules stationnés à {lieu}.",
            "plusieurs passants ont été blessés par des coups de machette après une tentative de vol à {lieu}.",
        ),
        (("F", 0.15), ("M", 0.45), ("E", 0.40)),
        (20, 21, 22, 23, 0, 1),
    ),
    IncidentScenario(
        "cambriolage_domicile",
        (
            "des bandits ont forcé la porte d'une habitation à {lieu} et emporté des biens de valeur.",
            "cambriolage signalé dans une maison à {lieu} ; les voisins ont alerté la police.",
            "des malfaiteurs armés sont entrés par effraction dans un domicile à {lieu} pendant l'absence des occupants.",
        ),
        (("F", 0.10), ("M", 0.50), ("E", 0.40)),
        (2, 3, 4, 22, 23, 0),
    ),
    IncidentScenario(
        "braquage_commerce",
        (
            "deux hommes en tenue civile armés ont braqué un bureau de change sur {axe} à {lieu}.",
            "tentative de braquage au supermarché à {lieu} ; des coups de feu ont été tirés en l'air.",
            "des individus armés ont intimidé le personnel d'un commerce à {lieu} avant de s'enfuir à moto.",
        ),
        (("F", 0.05), ("M", 0.35), ("E", 0.60)),
        (7, 8, 9, 17, 18, 19),
    ),
    IncidentScenario(
        "vol_rue",
        (
            "un pickpocket a dérobé un téléphone portable à un passant à {lieu}.",
            "vol à la tire signalé près du marché à {lieu}.",
            "un motard a arraché un sac à main sur {axe} à {lieu}.",
        ),
        (("F", 0.25), ("M", 0.55), ("E", 0.20)),
        (8, 12, 17, 18, 19, 20),
    ),
    IncidentScenario(
        "extorsion_transport",
        (
            "des jeunes exigent de l'argent aux passagers à l'arrêt {lieu} sur {axe}.",
            "extorsion signalée contre des vendeurs ambulants à {lieu}.",
            "un groupe bloque la circulation et réclame une contribution sur {axe} à {lieu}.",
        ),
        (("F", 0.20), ("M", 0.60), ("E", 0.20)),
        (16, 17, 18, 19, 20),
    ),
    IncidentScenario(
        "agression_sexuelle",
        (
            "une femme a été agressée dans une ruelle peu éclairée à {lieu} ; les voisins ont appelé la police.",
            "agression signalée contre une passante à {lieu} ; les auteurs se sont enfuis.",
        ),
        (("F", 0.05), ("M", 0.25), ("E", 0.70)),
        (20, 21, 22, 23, 0),
    ),
    IncidentScenario(
        "accident_circulation",
        (
            "accident de circulation avec dégâts matériels à {lieu} ; embouteillage important.",
            "collision entre un taxi et une moto sur {axe} à {lieu}, blessés légers signalés.",
        ),
        (("F", 0.70), ("M", 0.25), ("E", 0.05)),
        (7, 8, 17, 18, 19),
    ),
    IncidentScenario(
        "tapage_attroupement",
        (
            "tapage nocturne et attroupement nuisant au repos des habitants à {lieu}.",
            "bagarre entre passants à {lieu}, situation calmée par des voisins.",
            "pollution sonore persistante signalée à {lieu}.",
        ),
        (("F", 0.75), ("M", 0.20), ("E", 0.05)),
        (21, 22, 23, 0, 1),
    ),
    IncidentScenario(
        "vandalisme",
        (
            "vandalisme sur un véhicule stationné à {lieu}.",
            "des individus ont cassé des vitrines de boutiques à {lieu}.",
        ),
        (("F", 0.40), ("M", 0.45), ("E", 0.15)),
        (19, 20, 21, 22),
    ),
    IncidentScenario(
        "coups_feu",
        (
            "des coups de feu ont été entendus à {lieu} ; les passants se sont mis à l'abri.",
            "tirs en l'air lors d'une tentative de vol à {lieu}.",
        ),
        (("F", 0.10), ("M", 0.30), ("E", 0.60)),
        (21, 22, 23, 0, 1, 2),
    ),
)

AXES = [
    "l'avenue Libération",
    "l'avenue Monkoto",
    "l'avenue Kasa-Vubu",
    "l'avenue de la Paix",
    "le boulevard du 30 Juin",
    "la route Matadi-Kinshasa",
    "l'avenue Tombalbaye",
    "l'avenue de l'Université",
]


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text or "")
    stripped = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", stripped.lower()).strip()


def _fingerprint(description: str, lat: float, lon: float) -> str:
    payload = f"{_normalize_text(description)}|{lat:.4f}|{lon:.4f}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


class EmpiricalMarginals:
    """Distributions empiriques bootstrap depuis le CSV d'export (si présent)."""

    def __init__(self, hours: list[int], weekdays: list[int], degrees: list[str]):
        self.hours = hours or list(range(24))
        self.weekdays = weekdays or list(range(7))
        self.degrees = degrees or ["faible", "modéré", "élevé"]

    @classmethod
    def from_csv(cls, csv_path: Path) -> EmpiricalMarginals:
        if not csv_path.is_file():
            return cls([], [], [])
        try:
            df = pd.read_csv(csv_path)
        except Exception:
            return cls([], [], [])

        hours: list[int] = []
        weekdays: list[int] = []
        degrees: list[str] = []

        for _, row in df.iterrows():
            desc = str(row.get("description_report", "") or "")
            if len(desc.strip()) < 8 or desc.strip().lower() in {"kuluna", "vol", "tir", "dfd", "police"}:
                continue
            created = str(row.get("created_at", "") or "")
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                try:
                    dt = datetime.strptime(created[:19], fmt)
                    hours.append(dt.hour)
                    weekdays.append(dt.weekday())
                    break
                except ValueError:
                    continue
            deg = str(row.get("degree_report", "") or "").strip().lower()
            if deg in {"faible", "modéré", "modere", "élevé", "eleve"}:
                degrees.append(deg)

        return cls(hours, weekdays, degrees)


@dataclass
class SyntheticRecord:
    description: str
    location: str
    latitude: float
    longitude: float
    degree: str
    created_at: datetime
    commune_key: str
    quartier: str


class RealisticKinshasaGenerator:
    """Générateur avec déduplication et tirages statistiques."""

    def __init__(
        self,
        rng,
        *,
        marginals: EmpiricalMarginals | None = None,
        min_distance_m: float = 45.0,
        max_per_grid_cell: int = 4,
    ):
        self.rng = rng
        self.marginals = marginals or EmpiricalMarginals([], [], [])
        self.min_distance_m = min_distance_m
        self.max_per_grid_cell = max_per_grid_cell

        self._fingerprints: set[str] = set()
        self._descriptions: set[str] = set()
        self._coords: list[tuple[float, float]] = []
        self._grid_counts: dict[tuple[int, int], int] = {}

        commune_keys = [k for k in COMMUNE_CENTERS if k != "kinshasa"]
        weights = [COMMUNE_INCIDENCE_WEIGHTS.get(k, 1.0) for k in commune_keys]
        self._commune_keys = commune_keys
        self._commune_weights = weights

    def _pick_commune(self) -> str:
        return self.rng.choices(self._commune_keys, weights=self._commune_weights, k=1)[0]

    def _pick_quartier(self, commune_key: str) -> str:
        pool = list(COMMUNE_QUARTIERS.get(commune_key, []))
        for needle, (label, _lat, _lon) in QUARTIER_HINTS.items():
            if commune_key.replace(" ", "") in _normalize_text(label).replace(" ", ""):
                short = label.split(",")[0].replace("Quartier ", "").strip()
                if short and short not in pool:
                    pool.append(short)
        if not pool:
            return commune_key.title()
        return self.rng.choice(pool)

    def _pick_scenario(self) -> IncidentScenario:
        return self.rng.choice(INCIDENT_SCENARIOS)

    def _pick_degree(self, scenario: IncidentScenario) -> str:
        codes = [c for c, _ in scenario.degree_weights]
        weights = [w for _, w in scenario.degree_weights]
        code = self.rng.choices(codes, weights=weights, k=1)[0]
        return code

    def _pick_datetime(self, scenario: IncidentScenario) -> datetime:
        now = datetime.now()
        days_back = self.rng.randint(1, 540)
        base = now - timedelta(days=days_back)

        if self.marginals.hours:
            hour = self.rng.choice(self.marginals.hours)
        elif scenario.hour_bias:
            hour = self.rng.choice(scenario.hour_bias)
        else:
            hour = self.rng.randint(6, 23)

        if self.marginals.weekdays:
            weekday = self.rng.choice(self.marginals.weekdays)
            while base.weekday() != weekday:
                base -= timedelta(days=1)

        minute = self.rng.randint(0, 59)
        return base.replace(hour=hour, minute=minute, second=self.rng.randint(0, 59), microsecond=0)

    def _jitter_coords(self, commune_key: str) -> tuple[float, float]:
        for _ in range(60):
            lat, lon = random_point_near_commune(self.rng, commune_key)
            # Léger jitter supplémentaire pour éviter les points identiques
            lat += self.rng.gauss(0, 0.0012)
            lon += self.rng.gauss(0, 0.0012)
            if is_within_kinshasa_bounds(lat, lon) and not is_on_water_zone(lat, lon):
                return lat, lon
        return random_point_near_commune(self.rng, commune_key)

    def _grid_key(self, lat: float, lon: float) -> tuple[int, int]:
        return (int(round(lat * 800)), int(round(lon * 800)))

    def _too_close(self, lat: float, lon: float) -> bool:
        gk = self._grid_key(lat, lon)
        if self._grid_counts.get(gk, 0) >= self.max_per_grid_cell:
            return True
        for plat, plon in self._coords[-80:]:
            if _haversine_m(lat, lon, plat, plon) < self.min_distance_m:
                return True
        return False

    def _build_description(
        self,
        scenario: IncidentScenario,
        quartier: str,
        commune_key: str,
        dt: datetime,
    ) -> str:
        lieu = f"quartier {quartier}, commune {commune_key.title()}"
        axe = self.rng.choice(AXES)
        body = self.rng.choice(scenario.templates).format(lieu=lieu, axe=axe)

        jour = WEEKDAYS_FR[dt.weekday()]
        heure = dt.hour
        periode = _period_for_hour(heure)
        que_periode = _que_periode(periode)
        opener = self.rng.choice(TIME_OPENERS).format(
            jour=jour,
            heure=heure,
            minutes=dt.minute,
            periode=periode,
            que_periode=que_periode,
        )

        # Variantes de style citoyen
        suffixes = [
            "",
            " Les forces de l'ordre sont attendues sur place.",
            " Situation signalée aux autorités locales.",
            " Les habitants demandent un renfort de patrouille.",
            " Témoin : les auteurs se sont enfuis à moto.",
        ]
        text = f"{opener}, {body}{self.rng.choice(suffixes)}"

        # Casse légèrement variable (pas tout en minuscules)
        if self.rng.random() < 0.85:
            text = text[0].upper() + text[1:]

        return re.sub(r"\s+", " ", text).strip()

    def _is_duplicate(self, description: str, lat: float, lon: float) -> bool:
        fp = _fingerprint(description, lat, lon)
        if fp in self._fingerprints:
            return True
        norm_desc = _normalize_text(description)
        if norm_desc in self._descriptions:
            return True
        return False

    def _register(self, description: str, lat: float, lon: float) -> None:
        self._fingerprints.add(_fingerprint(description, lat, lon))
        self._descriptions.add(_normalize_text(description))
        self._coords.append((lat, lon))
        gk = self._grid_key(lat, lon)
        self._grid_counts[gk] = self._grid_counts.get(gk, 0) + 1

    def generate_one(self) -> SyntheticRecord | None:
        for _ in range(120):
            commune_key = self._pick_commune()
            quartier = self._pick_quartier(commune_key)
            scenario = self._pick_scenario()
            degree = self._pick_degree(scenario)
            dt = self._pick_datetime(scenario)
            lat, lon = self._jitter_coords(commune_key)

            if self._too_close(lat, lon):
                continue

            description = self._build_description(scenario, quartier, commune_key, dt)
            if self._is_duplicate(description, lat, lon):
                continue

            location = f"Quartier {quartier}, {commune_key.title()}, Kinshasa"
            self._register(description, lat, lon)

            return SyntheticRecord(
                description=description,
                location=location,
                latitude=lat,
                longitude=lon,
                degree=degree,
                created_at=dt,
                commune_key=commune_key,
                quartier=quartier,
            )
        return None

    def generate_many(self, count: int) -> tuple[list[SyntheticRecord], dict[str, Any]]:
        records: list[SyntheticRecord] = []
        failed = 0
        for _ in range(count):
            rec = self.generate_one()
            if rec is None:
                failed += 1
                continue
            records.append(rec)

        stats = {
            "requested": count,
            "created": len(records),
            "failed_retries": failed,
            "unique_fingerprints": len(self._fingerprints),
        }
        return records, stats


def load_marginals_from_prediction_csv() -> EmpiricalMarginals:
    from django.conf import settings

    csv_path = Path(settings.BASE_DIR) / "prediction" / "data" / "data_reports.csv"
    return EmpiricalMarginals.from_csv(csv_path)
