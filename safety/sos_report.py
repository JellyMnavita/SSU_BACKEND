"""Traitement des alertes SOS — validation système, hors modération IA classique."""

from __future__ import annotations

from django.utils import timezone

from reports.cache_utils import invalidate_reports_list_cache


def is_sos_report(report) -> bool:
    return getattr(report, "source", "") == "O"


def finalize_sos_report(report) -> None:
    """
    Valide automatiquement une alerte SOS sans passer par NLP/vision.
    Les SOS restent visibles dans le journal admin et le tableau de bord sécurité,
    mais sont exclus de la carte publique des incidents.
    """
    now = timezone.now()
    reasons = [
        "Alerte SOS — validation automatique système (hors modération IA classique).",
    ]

    report.status = "V"
    report.ai_processing_status = "skipped"
    report.ai_processed_at = now
    report.ai_processing_errors = None
    report.ai_moderation_recommendation = "V"
    report.ai_moderation_confidence = 1.0
    report.ai_moderation_reasons = reasons
    report.ai_moderation_auto_applied = True
    report.ai_enrichment_summary = {
        "skipped": True,
        "reason": "sos_emergency",
        "moderation": {
            "recommendation": "V",
            "confidence": 1.0,
            "reasons": reasons,
        },
    }
    report.save(
        update_fields=[
            "status",
            "ai_processing_status",
            "ai_processed_at",
            "ai_processing_errors",
            "ai_moderation_recommendation",
            "ai_moderation_confidence",
            "ai_moderation_reasons",
            "ai_moderation_auto_applied",
            "ai_enrichment_summary",
        ]
    )
    invalidate_reports_list_cache()
