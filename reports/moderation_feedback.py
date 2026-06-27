"""Retour humain sur la modération IA — utilisé pour l'apprentissage."""

from __future__ import annotations

from django.utils import timezone


def record_human_moderation_feedback(report, new_status: str, user) -> bool:
    """
    Mémorise quand un admin corrige la recommandation IA (ex. IA=Valider, humain=Rejeter).
    Stocké dans ai_enrichment_summary pour alimenter le réentraînement NLP.
    """
    ai_reco = (report.ai_moderation_recommendation or "").strip()
    if not ai_reco or ai_reco == new_status:
        return False

    summary = dict(report.ai_enrichment_summary or {})
    history = list(summary.get("human_feedback_history") or [])
    entry = {
        "final_status": new_status,
        "ai_recommendation": ai_reco,
        "ai_auto_applied": bool(report.ai_moderation_auto_applied),
        "at": timezone.now().isoformat(),
        "reviewer_id": getattr(user, "id", None) if user and user.is_authenticated else None,
    }
    history.append(entry)
    summary["human_feedback_history"] = history[-20:]
    summary["last_human_override"] = entry
    report.ai_enrichment_summary = summary
    report.save(update_fields=["ai_enrichment_summary"])
    return True
