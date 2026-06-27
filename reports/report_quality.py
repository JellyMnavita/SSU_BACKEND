"""Critères de qualité pour rejeter des signalements validés ou non fiables."""

from __future__ import annotations

from ai_gateway.services.content_filters import looks_benign, looks_non_security_news
from locations.geo_validation import coordinate_quality_issue

SYNTHETIC_URL_PREFIX = "synthetic://training/"


def is_synthetic_training_report(report) -> bool:
    url = (getattr(report, "external_source_url", "") or "").strip()
    return url.startswith(SYNTHETIC_URL_PREFIX)


_USER_SOURCES = frozenset({"U", "C", "O", "Q", "W"})


def get_rejection_reason(report) -> str | None:
    """Retourne une raison de rejet ou None si le signalement semble acceptable."""
    description = report.description or ""

    if looks_benign(description):
        return "contenu anodin / blague"

    if looks_non_security_news(description):
        return "actualité non liée à la sécurité urbaine"

    # Ne pas rejeter automatiquement les signalements citoyens sur heuristique GPS/eau :
    # risque de faux positifs (ex. Mont Ngafula, Selembao). La validation à la création reste active.
    if getattr(report, "source", "") in _USER_SOURCES:
        return None

    geo_issue = coordinate_quality_issue(
        report.latitude,
        report.longitude,
        location=report.location,
        quartier=report.quartier,
    )
    if geo_issue:
        return geo_issue

    return None
