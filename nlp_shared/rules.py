"""Correspondance des règles lexique."""

from __future__ import annotations

import re

from nlp_shared.lexicon_data import RULES

_NEGATION_BEFORE_MATCH = re.compile(
    r"(?:"
    r"\b(?:pas|aucun|sans|jamais|rien|non|n'?est)\b"
    r"(?:\s+(?:du\s+)?tout|\s+de|\s+d'|\s+un|\s+une|\s+le|\s+la|\s+les|\s+des|\s+si|\s+très|\s+trop)?"
    r"){1,3}\s*$",
    re.IGNORECASE,
)


def _is_negated_match(text: str, match: re.Match[str]) -> bool:
    """Ignore les mots-clés précédés d'une négation (« pas dangereux », etc.)."""
    if match.start() <= 0:
        return False
    window = text[max(0, match.start() - 48) : match.start()]
    if not window.strip():
        return False
    return bool(_NEGATION_BEFORE_MATCH.search(window))


def match_rule(text: str) -> tuple[str, float, str] | None:
    """
    Retourne (label, confiance, pattern_id) pour la meilleure règle correspondante.
    pattern_id = index de la règle (debug).
    """
    best: tuple[str, float, int] | None = None
    for idx, (pattern, label, confidence) in enumerate(RULES):
        found = re.search(pattern, text, re.IGNORECASE)
        if not found or _is_negated_match(text, found):
            continue
        if best is None or confidence > best[1]:
            best = (label, confidence, idx)
    if best is None:
        return None
    return best[0], best[1], f"rule_{best[2]}"
