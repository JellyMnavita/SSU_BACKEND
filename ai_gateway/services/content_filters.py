"""Filtres de contenu — garde-fous modération (actualités, contenus anodins).

Source unique des patterns : ``nlp_shared`` (partagé avec le microservice NLP).
"""

from __future__ import annotations

from nlp_shared.filters import (
    has_local_incident_markers,
    keywords_risk,
    looks_benign,
    looks_non_security_news,
)

__all__ = [
    "has_local_incident_markers",
    "keywords_risk",
    "looks_benign",
    "looks_non_security_news",
]
