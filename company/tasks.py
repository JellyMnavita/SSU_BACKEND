"""Tâches Celery — rapports hebdomadaires organisation."""

from __future__ import annotations

import logging

from celery import shared_task

from .weekly_report import send_weekly_report_email, users_for_weekly_reports

logger = logging.getLogger(__name__)


@shared_task(name="company.tasks.send_weekly_security_reports")
def send_weekly_security_reports(dry_run: bool = False):
    """
    Envoie le rapport hebdomadaire aux utilisateurs avec weekly_report activé.
    Les comptes COMPANY reçoivent la synthèse organisation (sites, alertes, communes).
    """
    sent = 0
    skipped = 0
    errors = 0

    for user in users_for_weekly_reports():
        prefs = user.merged_notification_preferences()
        if not prefs.get("weekly_report", True):
            skipped += 1
            continue
        try:
            if send_weekly_report_email(user, dry_run=dry_run):
                sent += 1
            else:
                skipped += 1
        except Exception:
            errors += 1
            logger.exception("Échec envoi rapport hebdo user_id=%s", user.pk)

    result = {"sent": sent, "skipped": skipped, "errors": errors, "dry_run": dry_run}
    logger.info("Rapports hebdomadaires terminés: %s", result)
    return result
