"""Lexique et filtres NLP partagés (service nlp + Django ai_gateway)."""

from nlp_shared.filters import (
    has_local_incident_markers,
    is_benign_content,
    looks_benign,
    looks_non_security_news,
)
from nlp_shared.lexicon_data import BENIGN_PATTERNS, INCIDENT_TYPES, RULES, SEED_SAMPLES
from nlp_shared.rules import match_rule

__all__ = [
    "BENIGN_PATTERNS",
    "INCIDENT_TYPES",
    "RULES",
    "SEED_SAMPLES",
    "has_local_incident_markers",
    "is_benign_content",
    "looks_benign",
    "looks_non_security_news",
    "match_rule",
]
