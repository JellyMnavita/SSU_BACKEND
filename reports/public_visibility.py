"""Visibilité publique des signalements sur la carte (fenêtre glissante)."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone


def get_public_map_retention_days() -> int:
    from .models import ReportAISettings

    raw = ReportAISettings.get_solo().public_map_retention_days
    try:
        days = int(raw if raw is not None else 30)
    except (TypeError, ValueError):
        days = 30
    return max(0, min(days, 365))


def apply_public_map_retention(qs):
    """Filtre les signalements trop anciens pour la carte publique (0 = illimité)."""
    days = get_public_map_retention_days()
    if days <= 0:
        return qs
    since = timezone.now() - timedelta(days=days)
    return qs.filter(created_at__gte=since)
