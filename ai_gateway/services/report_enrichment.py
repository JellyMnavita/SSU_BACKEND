"""Enrichissement IA d'un signalement (NLP + vision)."""

from __future__ import annotations

import logging
import os

from django.conf import settings
from django.core.files.storage import default_storage

from ai_gateway.clients import NLPServiceClient, VisionServiceClient
from ai_gateway.clients.base import AIServiceError
from .content_filters import looks_non_security_news
from .degree_adjustment import apply_degree_adjustment

logger = logging.getLogger(__name__)


def enrich_report_with_ai(report) -> dict:
    """
    Appelle nlp-service et vision-service.
    Ne lève pas d'exception : retourne les métadonnées IA ou des erreurs partielles.
    """
    if not getattr(settings, "AI_GATEWAY_ENABLED", True):
        return {"skipped": True, "reason": "AI_GATEWAY_DISABLED"}

    result = {
        "nlp": None,
        "vision": None,
        "errors": [],
    }

    nlp_client = NLPServiceClient()
    vision_client = VisionServiceClient()

    if report.description:
        try:
            result["nlp"] = nlp_client.classify_text(report.description)
            if looks_non_security_news(report.description):
                result["nlp"] = {
                    "incident_type": "autre",
                    "confidence": 0.88,
                    "model_used": "institutional_filter",
                    "original_nlp": result["nlp"],
                }
        except AIServiceError as exc:
            logger.error("NLP enrichment failed: %s", exc)
            result["errors"].append({"service": "nlp", "detail": str(exc)})

    if report.picture:
        try:
            picture_name = report.picture.name
            with default_storage.open(picture_name, "rb") as image_file:
                image_bytes = image_file.read()
            filename = os.path.basename(picture_name) or "report.jpg"
            result["vision"] = vision_client.analyze_image(image_bytes, filename)
        except AIServiceError as exc:
            logger.error("Vision enrichment failed: %s", exc)
            result["errors"].append({"service": "vision", "detail": str(exc)})
        except Exception as exc:
            logger.error("Vision read failed: %s", exc)
            result["errors"].append({"service": "vision", "detail": str(exc)})

    return result


def apply_enrichment_to_report(report, enrichment: dict) -> None:
    """Persiste les champs IA sur le modèle Report."""
    nlp = enrichment.get("nlp") or {}
    vision = enrichment.get("vision") or {}

    if nlp.get("incident_type"):
        report.ai_incident_type = nlp["incident_type"]
        report.ai_nlp_confidence = nlp.get("confidence")
    if vision.get("detected_objects") is not None:
        report.ai_vision_results = vision

    update_fields = []
    if nlp.get("incident_type"):
        update_fields.extend(["ai_incident_type", "ai_nlp_confidence"])
    if vision.get("detected_objects") is not None:
        update_fields.append("ai_vision_results")

    if update_fields:
        report.save(update_fields=update_fields)


def apply_ai_to_report(report, enrichment: dict) -> dict:
    """Persiste enrichissement NLP/vision puis ajuste le degré de danger."""
    from .fusion import compute_fusion

    apply_enrichment_to_report(report, enrichment)
    degree_meta = apply_degree_adjustment(report, enrichment)
    enrichment["degree"] = degree_meta
    enrichment["fusion"] = compute_fusion(
        report.description or "",
        enrichment.get("nlp"),
        enrichment.get("vision"),
    )
    return enrichment
