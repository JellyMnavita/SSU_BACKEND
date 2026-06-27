"""Filtre de pertinence sécurité + Kinshasa."""

from __future__ import annotations

import re
import unicodedata

# Mots-clés sécurité (titres d'actualité RDC)
SECURITY_KEYWORDS = [
    "insecurit",
    "securit",
    "police",
    "armee",
    "arme",
    "fusillade",
    "tir",
    "meurtre",
    "assassinat",
    "homicide",
    "agression",
    "violence",
    "vol",
    "braquage",
    "cambriolage",
    "kidnapping",
    "enlevement",
    "otage",
    "bandit",
    "gang",
    "incendie",
    "accident",
    "mort",
    "deces",
    "blesse",
    "victime",
    "corps",
    "emeute",
    "manifestation",
    "attentat",
    "attaque",
    "terror",
    "adf",
    "m23",
    "fardc",
    "milice",
    "wazalendo",
    "affrontement",
    "bombardement",
    "rebelle",
    "pillag",
    "effraction",
    "cambriol",
    "hold-up",
    "hold up",
    "agresseur",
    "criminel",
    "delinquant",
]

# Provinces / villes hors Kinshasa (détection pour message explicite)
OUTSIDE_KINSHASA_MARKERS: list[tuple[str, str]] = [
    ("sud-kivu", "Sud-Kivu"),
    ("nord-kivu", "Nord-Kivu"),
    ("ituri", "Ituri"),
    ("beni", "Beni"),
    ("butembo", "Butembo"),
    ("goma", "Goma"),
    ("bukavu", "Bukavu"),
    ("uvira", "Uvira"),
    ("mambasa", "Mambasa"),
    ("kasai", "Kasaï"),
    ("lubumbashi", "Lubumbashi"),
    ("katanga", "Katanga"),
    ("equateur", "Équateur"),
    ("m23", "zone M23"),
    ("adf", "zone ADF"),
    ("baraka", "Baraka (Sud-Kivu)"),
    ("mikenge", "Mikenge (Sud-Kivu)"),
    ("fizi", "Fizi (Sud-Kivu)"),
    ("itombwe", "Itombwe"),
    ("rutshuru", "Rutshuru"),
    ("masisi", "Masisi"),
    ("mwenga", "Mwenga"),
    ("est de la rdc", "Est de la RDC"),
]

KINSHASA_PATTERN = re.compile(r"\bkinshasa\b", re.IGNORECASE)


def normalize_text(text: str) -> str:
    """Retire les accents pour un matching fiable (Insécurité → insecurite)."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in normalized if not unicodedata.combining(c))
    return stripped.lower()


def find_security_keywords(text: str) -> list[str]:
    norm = normalize_text(text)
    return [kw for kw in SECURITY_KEYWORDS if kw in norm]


def is_security_related(text: str) -> bool:
    return bool(find_security_keywords(text))


def is_institutional_news(text: str) -> bool:
    from ai_gateway.services.content_filters import looks_non_security_news

    return looks_non_security_news(text)


def explain_institutional_rejection(text: str) -> str:
    return (
        "Filtre institutionnel : article politique, administratif ou de politique publique "
        "(ex. RDC-PASS, transformation numérique, cérémonie officielle) — "
        "pas un incident de sécurité urbaine à cartographier."
    )


def mentions_kinshasa(text: str) -> bool:
    return bool(KINSHASA_PATTERN.search(text or ""))


def detect_outside_kinshasa_region(text: str) -> str | None:
    norm = normalize_text(text)
    for marker, label in OUTSIDE_KINSHASA_MARKERS:
        if marker in norm:
            return label
    return None


def incident_location_outside_kinshasa(title: str, content: str = "") -> tuple[bool, str | None]:
    """
    L'incident est-il hors Kinshasa ?
    Le titre prime (format presse « Province : … »). Kinshasa dans le corps seul
    ne suffit pas si le titre situe l'actu ailleurs.
    """
    title_norm = normalize_text(title)
    if "kinshasa" in title_norm:
        return False, None

    region_in_title = detect_outside_kinshasa_region(title)
    if region_in_title:
        return True, region_in_title

    # Intro de l'article (lieu de l'incident) avant mentions accessoires à Kinshasa
    intro = normalize_text((content or "")[:500])
    region_in_intro = detect_outside_kinshasa_region(intro)
    if region_in_intro and "kinshasa" not in intro:
        return True, region_in_intro

    return False, None


def explain_outside_kinshasa_incident(region: str | None, title: str = "") -> str:
    base = (
        f"Hors zone Kinshasa : l'incident concerne {region or 'une autre province'}. "
        "SSU ne cartographie que Kinshasa."
    )
    if title and "kinshasa" not in normalize_text(title):
        base += (
            " Une simple mention de Kinshasa dans le texte (convocation, déplacement, etc.) "
            "ne place pas l'incident à Kinshasa."
        )
    return base


def explain_security_rejection(text: str) -> str:
    """Motif détaillé si l'article n'est pas retenu au filtre sécurité."""
    if is_security_related(text):
        return ""
    return (
        "Filtre sécurité : aucun mot-clé reconnu dans le titre ou le contenu "
        "(ex. attaque, insécurité, vol, victime, police…). "
        "Le corps de l'article n'a peut-être pas été récupéré."
    )


def explain_geo_rejection(text: str) -> str:
    """Motif détaillé si l'article est hors zone Kinshasa."""
    region = detect_outside_kinshasa_region(text)
    if region:
        return (
            f"Hors zone Kinshasa : l'article concerne {region}. "
            "SSU cartographie uniquement Kinshasa — les actualités des autres "
            "provinces sont ignorées volontairement."
        )
    if mentions_kinshasa(text):
        return (
            "Kinshasa mentionné mais aucun quartier/commune identifiable "
            "dans la base SSU."
        )
    return (
        "Hors zone Kinshasa : aucune mention de Kinshasa ni de quartier connu. "
        "Seules les actualités localisables à Kinshasa deviennent des signalements."
    )


def build_description(title: str, content: str, max_len: int = 2000) -> str:
    title = (title or "").strip()
    content = (content or "").strip()
    if content and title.lower() not in content.lower()[:200]:
        body = f"{title}\n\n{content}"
    else:
        body = content or title
    return body[:max_len]
