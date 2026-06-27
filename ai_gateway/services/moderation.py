"""Recommandation de modération (valider / rejeter / en attente) via fusion IA."""

from __future__ import annotations

from .fusion import compute_fusion, moderation_from_fusion


def _reject_settings_from_db() -> dict:
    from reports.models import ReportAISettings

    s = ReportAISettings.get_solo()
    return {
        "auto_reject_enabled": s.auto_reject_enabled,
        "auto_reject_citizen_reports": s.auto_reject_citizen_reports,
        "auto_reject_score_threshold": s.auto_reject_score_threshold,
    }


def compute_ai_moderation(report, enrichment: dict) -> dict:
    """
    Produit une recommandation V (valider), R (rejeter) ou P (en attente).
    S'appuie sur le score de risque fusionné NLP + vision.
    """
    description = (report.description or "").strip()
    fusion = compute_fusion(
        description,
        enrichment.get("nlp"),
        enrichment.get("vision"),
    )
    return moderation_from_fusion(
        description,
        enrichment,
        fusion,
        report_source=getattr(report, "source", "") or "",
        reject_settings=_reject_settings_from_db(),
    )


def apply_moderation_to_report(report, moderation: dict, enrichment: dict) -> None:
    """Persiste la recommandation IA et un résumé d'enrichissement."""
    degree_meta = enrichment.get("degree") or {}
    fusion = compute_fusion(
        report.description or "",
        enrichment.get("nlp"),
        enrichment.get("vision"),
    )
    report.ai_moderation_recommendation = moderation["recommendation"]
    report.ai_moderation_confidence = moderation.get("confidence")
    report.ai_moderation_reasons = moderation.get("reasons") or []
    report.ai_enrichment_summary = {
        "nlp": enrichment.get("nlp"),
        "vision": enrichment.get("vision"),
        "errors": enrichment.get("errors"),
        "degree": degree_meta,
        "fusion": fusion,
        "moderation": moderation,
    }
    report.save(
        update_fields=[
            "ai_moderation_recommendation",
            "ai_moderation_confidence",
            "ai_moderation_reasons",
            "ai_enrichment_summary",
        ]
    )
