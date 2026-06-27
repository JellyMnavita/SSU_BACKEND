"""Liaison signalements citoyen (sans compte) ↔ compte utilisateur."""

from __future__ import annotations

from django.contrib.auth import get_user_model

from reports.models import Report

User = get_user_model()


def link_citizen_reports_to_user(user: User) -> int:
    """
    Rattache à un compte SSU les signalements déposés avant inscription
    (source C, enregistrés via citizen.email).
    """
    if not user.email:
        return 0
    return Report.objects.filter(
        citizen__email__iexact=user.email.strip(),
        user__isnull=True,
    ).update(user=user)
