"""Paramètres et application automatique de la modération IA."""

from __future__ import annotations

import logging

from .cache_utils import invalidate_reports_list_cache
from ai_gateway.services.content_filters import looks_benign, looks_non_security_news
from locations.geo_validation import coordinate_quality_issue

logger = logging.getLogger(__name__)


def maybe_auto_apply_moderation(report, moderation: dict) -> bool:
    """
    Si activé dans les paramètres admin, applique V/R/P au statut du signalement.
    Retourne True si le statut a été modifié.
    """
    from .models import ReportAISettings

    # SOS : toujours validé par le système, jamais rejeté par l'auto-modération IA.
    if report.source == "O":
        reco = moderation.get("recommendation")
        if reco == "V" and report.status != "V":
            previous = report.status
            report.status = "V"
            report.ai_moderation_auto_applied = True
            report.save(update_fields=["status", "ai_moderation_auto_applied"])
            invalidate_reports_list_cache()
            from .notifications import notify_report_status_change

            notify_report_status_change(report, previous)
            logger.info(
                "Auto-modération SOS signalement %s : %s → V",
                report.pk,
                previous,
            )
            return True
        return False

    settings = ReportAISettings.get_solo()
    if not settings.auto_apply_moderation:
        return False

    reco = moderation.get("recommendation")
    if reco not in ("V", "R", "P"):
        return False

    if reco == "R" and not settings.auto_reject_enabled:
        return False
    if (
        reco == "R"
        and report.source in ("C", "U", "W", "Q")
        and not settings.auto_reject_citizen_reports
    ):
        return False

    # Articles scrapés : pour éviter trop de charge admin, on autorise l'auto-validation
    # uniquement si la confiance est très élevée + garde-fous contenu/géoloc.
    if report.source == "S" and reco == "V":
        confidence = float(moderation.get("confidence") or 0.0)
        if confidence < 0.90:
            return False

        description = (getattr(report, "description", "") or "").strip()
        if looks_benign(description) or looks_non_security_news(description):
            return False

        geo_issue = coordinate_quality_issue(
            getattr(report, "latitude", None),
            getattr(report, "longitude", None),
            location=getattr(report, "location", None),
            quartier=getattr(report, "quartier", None),
        )
        if geo_issue:
            return False

    if report.status == reco:
        return False

    previous = report.status
    report.status = reco
    report.ai_moderation_auto_applied = True
    report.save(update_fields=["status", "ai_moderation_auto_applied"])
    invalidate_reports_list_cache()
    from .notifications import notify_report_status_change

    notify_report_status_change(report, previous)
    logger.info(
        "Auto-modération IA signalement %s : %s → %s (reco %s)",
        report.pk,
        previous,
        reco,
        reco,
    )
    return True
