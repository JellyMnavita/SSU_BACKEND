"""Correction admin de la classe vision + export automatique au dataset."""

from __future__ import annotations

from pathlib import Path

from django.utils import timezone

from .vision_dataset import VISION_LABELS, export_image_to_labeled


def _predicted_label(report) -> str:
    vision = report.ai_vision_results or {}
    objects = vision.get("detected_objects") or []
    if not objects:
        return ""
    return str(objects[0].get("label") or "")


def apply_vision_label_correction(
    report,
    correct_label: str,
    *,
    reviewer_id: int | None = None,
    trigger_retrain_check: bool = True,
) -> dict:
    """
    Corrige la classe vision, exporte la photo vers labeled/<classe>/
    et enregistre le feedback dans ai_enrichment_summary.
    """
    correct_label = (correct_label or "").strip().lower()
    if correct_label not in VISION_LABELS:
        raise ValueError(f"Classe invalide : {correct_label}")
    if not report.picture:
        raise ValueError("Ce signalement n'a pas de photo.")

    summary = dict(report.ai_enrichment_summary or {})
    previous = summary.get("vision_dataset_export") or {}
    previous_rel = previous.get("path")

    src = Path(report.picture.path)
    export = export_image_to_labeled(
        src,
        correct_label,
        suffix=f"rpt{report.id}",
        previous_rel=previous_rel,
    )

    predicted = _predicted_label(report)
    entry = {
        "correct_label": correct_label,
        "predicted_label": predicted,
        "path": export["path"],
        "sha256": export["sha256"],
        "duplicate": export.get("duplicate", False),
        "at": timezone.now().isoformat(),
        "reviewer_id": reviewer_id,
    }

    history = list(summary.get("vision_feedback_history") or [])
    history.append(entry)
    summary["vision_feedback_history"] = history[-30:]
    summary["vision_dataset_export"] = entry
    summary["vision_corrected_label"] = correct_label

    vision = dict(report.ai_vision_results or {})
    objects = list(vision.get("detected_objects") or [])
    if objects:
        objects[0] = {
            **objects[0],
            "label": correct_label,
            "admin_corrected": True,
            "original_label": predicted or objects[0].get("label"),
        }
    else:
        objects = [{"label": correct_label, "confidence": 1.0, "admin_corrected": True}]
    vision["detected_objects"] = objects
    vision["admin_corrected_label"] = correct_label

    report.ai_enrichment_summary = summary
    report.ai_vision_results = vision
    report.save(update_fields=["ai_enrichment_summary", "ai_vision_results"])

    retrain_queued = False
    if trigger_retrain_check:
        retrain_queued = _maybe_queue_auto_retrain()

    return {**export, "predicted_label": predicted, "retrain_queued": retrain_queued}


def _maybe_queue_auto_retrain() -> bool:
    from django.core.cache import cache

    from .models import ReportAISettings
    from .vision_dataset import EXPORTS_SINCE_TRAIN_KEY

    settings_obj = ReportAISettings.get_solo()
    threshold = int(settings_obj.vision_retrain_after_exports or 0)
    if threshold <= 0:
        return False

    count = int(cache.get(EXPORTS_SINCE_TRAIN_KEY) or 0)
    if count < threshold:
        return False

    from .tasks import train_ai_models

    if cache.get("ai:train:running"):
        return False

    train_ai_models.delay(model="vision")
    return True
