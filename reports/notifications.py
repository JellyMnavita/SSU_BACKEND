"""Notifications in-app lorsque le statut d'un signalement change."""

from __future__ import annotations

import logging

from django.db.models import Q

logger = logging.getLogger(__name__)

STATUS_MESSAGES = {
    "V": "Votre signalement RPT-{report_id} a été validé et pris en compte.",
    "R": "Votre signalement RPT-{report_id} a été rejeté après examen.",
}


def _report_recipients(report):
    from users.models import User

    recipients: list = []
    seen: set[int] = set()

    if report.user_id:
        recipients.append(report.user)
        seen.add(report.user_id)

    citizen = getattr(report, "citizen", None)
    if citizen and citizen.email:
        matched = User.objects.filter(email__iexact=citizen.email).first()
        if matched and matched.pk not in seen:
            recipients.append(matched)
            seen.add(matched.pk)

    return recipients


def notify_report_status_change(report, previous_status: str) -> int:
    """
    Crée une notification in-app pour le(s) auteur(s) lorsque le statut passe à V ou R.
    Retourne le nombre de notifications créées.
    """
    from .models import ReportNotification

    if report.status == previous_status:
        return 0
    if report.status not in ("V", "R"):
        return 0
    if previous_status not in ("P", "") and report.status == previous_status:
        return 0

    message_tpl = STATUS_MESSAGES.get(report.status)
    if not message_tpl:
        return 0

    message = message_tpl.format(report_id=report.pk)
    created = 0

    for recipient in _report_recipients(report):
        _, was_created = ReportNotification.objects.get_or_create(
            recipient=recipient,
            report=report,
            status=report.status,
            defaults={"message": message},
        )
        if was_created:
            created += 1
            logger.info(
                "Notification signalement %s → user %s (%s)",
                report.pk,
                recipient.pk,
                report.status,
            )

    return created


def update_report_status(report, new_status: str, *, notify: bool = True) -> bool:
    """Met à jour le statut et déclenche la notification si besoin."""
    previous = report.status
    if previous == new_status:
        return False
    report.status = new_status
    report.save(update_fields=["status"])
    if notify:
        notify_report_status_change(report, previous)
    return True
