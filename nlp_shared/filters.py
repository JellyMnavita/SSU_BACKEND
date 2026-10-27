"""Filtres de contenu unifiés (anodin, actualités, marqueurs locaux)."""

from __future__ import annotations

import re

from nlp_shared.lexicon_data import (
    BENIGN_CONTEXT_PATTERNS,
    BENIGN_STRICT_PATTERNS,
    HIGH_RISK_KEYWORD_PATTERN,
    LOCAL_INCIDENT_MARKERS,
    MEDIUM_RISK_KEYWORD_PATTERN,
)

_BENIGN_STRICT_RE = re.compile("|".join(f"(?:{p})" for p in BENIGN_STRICT_PATTERNS), re.IGNORECASE)
_BENIGN_CONTEXT_RE = re.compile("|".join(f"(?:{p})" for p in BENIGN_CONTEXT_PATTERNS), re.IGNORECASE)
_LOCAL_INCIDENT_RE = re.compile("|".join(f"(?:{p})" for p in LOCAL_INCIDENT_MARKERS), re.IGNORECASE)
_HIGH_RISK_RE = re.compile(HIGH_RISK_KEYWORD_PATTERN, re.IGNORECASE)
_MEDIUM_RISK_RE = re.compile(MEDIUM_RISK_KEYWORD_PATTERN, re.IGNORECASE)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def has_local_incident_markers(description: str) -> bool:
    return bool(_LOCAL_INCIDENT_RE.search(description or ""))


def is_benign_strict(text: str) -> bool:
    """Tests, blagues — toujours rejetés."""
    return bool(_BENIGN_STRICT_RE.search(_normalize(text)))


def is_benign_contextual(text: str) -> bool:
    """Actualités / hors périmètre — rejetés sauf si incident local signalé."""
    normalized = _normalize(text)
    if not _BENIGN_CONTEXT_RE.search(normalized):
        return False
    return not has_local_incident_markers(normalized)


def is_benign_content(text: str) -> bool:
    """Filtre anodin complet pour le service NLP."""
    return is_benign_strict(text) or is_benign_contextual(text)


def looks_benign(description: str) -> bool:
    """Alias Django — tests et blagues uniquement (comportement fusion historique)."""
    return is_benign_strict(description)


def looks_non_security_news(description: str) -> bool:
    """Article d'actualité générale, pas un signalement d'incident urbain."""
    return is_benign_contextual(description)


def benign_match_reason(text: str) -> str | None:
    """Raison du rejet anodin (debug / évaluation)."""
    normalized = _normalize(text)
    if _BENIGN_STRICT_RE.search(normalized):
        return "strict"
    if is_benign_contextual(normalized):
        return "contextual"
    return None


def keywords_risk(description: str) -> tuple[float, str]:
    if not description:
        return 0.0, ""
    if looks_non_security_news(description):
        return 0.0, ""
    if _HIGH_RISK_RE.search(description):
        return 0.90, "Mots-clés : alerte critique"
    if _MEDIUM_RISK_RE.search(description):
        return 0.55, "Mots-clés : vigilance"
    if has_local_incident_markers(description):
        return 0.55, "Mots-clés : incident local signalé"
    return 0.0, ""
