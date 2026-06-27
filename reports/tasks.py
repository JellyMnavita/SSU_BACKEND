"""Tâches Celery — enrichissement IA asynchrone des signalements."""

from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from ai_gateway.services.moderation import (
    apply_moderation_to_report,
    compute_ai_moderation,
)
from ai_gateway.services.report_enrichment import (
    apply_ai_to_report,
    enrich_report_with_ai,
)

from .ai_settings import maybe_auto_apply_moderation
from .cache_utils import invalidate_reports_list_cache

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="reports.tasks.process_report_ai",
    max_retries=2,
    default_retry_delay=30,
)
def process_report_ai(self, report_id: int):
    from .models import Report

    try:
        report = Report.objects.get(pk=report_id)
    except Report.DoesNotExist:
        logger.warning("process_report_ai: report %s introuvable", report_id)
        return

    from .report_quality import is_synthetic_training_report

    if is_synthetic_training_report(report):
        report.ai_processing_status = "skipped"
        report.ai_processed_at = timezone.now()
        report.save(update_fields=["ai_processing_status", "ai_processed_at"])
        return

    if report.source == "O":
        from safety.sos_report import finalize_sos_report

        finalize_sos_report(report)
        return

    if report.ai_processing_status in ("completed", "skipped"):
        return

    report.ai_processing_status = "processing"
    report.save(update_fields=["ai_processing_status"])

    try:
        if not getattr(settings, "AI_GATEWAY_ENABLED", True):
            report.ai_processing_status = "skipped"
            report.ai_processed_at = timezone.now()
            report.save(update_fields=["ai_processing_status", "ai_processed_at"])
            invalidate_reports_list_cache()
            return

        enrichment = enrich_report_with_ai(report)
        apply_ai_to_report(report, enrichment)
        moderation = compute_ai_moderation(report, enrichment)
        apply_moderation_to_report(report, moderation, enrichment)
        auto_applied = maybe_auto_apply_moderation(report, moderation)

        report.ai_processing_status = "completed"
        report.ai_processing_errors = enrichment.get("errors") or None
        report.ai_processed_at = timezone.now()
        report.save(
            update_fields=[
                "ai_processing_status",
                "ai_processing_errors",
                "ai_processed_at",
            ]
        )
        invalidate_reports_list_cache()
        logger.info(
            "IA terminée pour signalement %s — reco %s%s",
            report_id,
            moderation.get("recommendation"),
            " (auto-appliquée)" if auto_applied else "",
        )
    except Exception as exc:
        logger.exception("process_report_ai failed for report %s", report_id)
        report.ai_processing_status = "failed"
        report.ai_processing_errors = [{"detail": str(exc)}]
        report.ai_processed_at = timezone.now()
        report.save(
            update_fields=[
                "ai_processing_status",
                "ai_processing_errors",
                "ai_processed_at",
            ]
        )
        invalidate_reports_list_cache()
        raise self.retry(exc=exc)


NLP_LABELS = frozenset(
    {"violence", "vol", "kidnapping", "agression", "vandalisme", "autre"}
)
DEGREE_TO_NLP_LABEL = {"F": "autre", "M": "vol", "E": "violence"}


def _nlp_training_samples(limit: int = 400) -> list[dict]:
    from django.db.models import F

    from .models import Report

    samples: list[dict] = []
    seen: set[int] = set()

    def add_sample(report: Report, label: str) -> None:
        if report.id in seen or len(samples) >= limit:
            return
        text = (report.description or "").strip()
        if len(text) < 15:
            return
        from ai_gateway.services.content_filters import looks_non_security_news

        if looks_non_security_news(text):
            label = "autre"
        label = label if label in NLP_LABELS else "autre"
        samples.append({"text": text[:2000], "label": label})
        seen.add(report.id)

    # Priorité : corrections humaines (IA ≠ décision finale)
    overrides = (
        Report.objects.filter(status__in=["V", "R"])
        .exclude(ai_moderation_recommendation="")
        .exclude(description="")
        .exclude(ai_moderation_recommendation=F("status"))
        .order_by("-created_at")[: max(limit // 3, 40)]
    )
    for report in overrides:
        if report.status == "R":
            label = "autre"
        else:
            label = (report.ai_incident_type or "").strip().lower()
            if label not in NLP_LABELS:
                label = DEGREE_TO_NLP_LABEL.get(report.degree, "autre")
        # Renforcer les corrections humaines (IA ≠ décision finale).
        for _ in range(3):
            add_sample(report, label)

    validated = (
        Report.objects.filter(status="V")
        .exclude(description="")
        .order_by("-created_at")[: max(limit // 2, 80)]
    )
    for report in validated:
        label = (report.ai_incident_type or "").strip().lower()
        if label not in NLP_LABELS:
            label = DEGREE_TO_NLP_LABEL.get(report.degree, "autre")
        add_sample(report, label)

    rejected = (
        Report.objects.filter(status="R")
        .exclude(description="")
        .order_by("-created_at")[: max(limit // 3, 60)]
    )
    for report in rejected:
        add_sample(report, "autre")

    return samples[:limit]


def _nlp_corpus_file_samples(limit: int = 2500) -> list[dict]:
    """Charge train.csv + val.csv depuis NLP_DATA_DIR (Phase 2)."""
    import csv
    import os
    from pathlib import Path

    data_dir = Path(os.environ.get("NLP_DATA_DIR", Path(settings.BASE_DIR).parent / "nlp_data"))
    samples: list[dict] = []
    seen: set[str] = set()

    for filename in ("train.csv", "val.csv"):
        path = data_dir / filename
        if not path.is_file():
            continue
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                text = (row.get("text") or "").strip()
                label = (row.get("label") or "").strip().lower()
                if len(text) < 15 or label not in NLP_LABELS:
                    continue
                key = text[:500].lower()
                if key in seen:
                    continue
                seen.add(key)
                samples.append({"text": text[:2000], "label": label})
                if len(samples) >= limit:
                    return samples
    return samples


def _merged_nlp_training_samples() -> list[dict]:
    corpus = _nlp_corpus_file_samples()
    if len(corpus) >= 50:
        return corpus
    db_samples = _nlp_training_samples()
    seen = {s["text"][:500].lower() for s in corpus}
    for sample in db_samples:
        key = sample["text"][:500].lower()
        if key not in seen:
            corpus.append(sample)
            seen.add(key)
    return corpus


def _train_nlp_model() -> dict:
    if not getattr(settings, "AI_USE_MICROSERVICES", True):
        return {"status": "skipped", "reason": "microservices désactivés"}

    import os
    from pathlib import Path

    from ai_gateway.clients.nlp import NLPServiceClient

    data_dir = Path(os.environ.get("NLP_DATA_DIR", Path(settings.BASE_DIR).parent / "nlp_data"))
    use_corpus = (data_dir / "train.csv").is_file() and (data_dir / "val.csv").is_file()
    # Toujours fusionner les signalements modérés (validés/rejetés/corrections humaines).
    db_samples = _nlp_training_samples()
    return NLPServiceClient().train(db_samples, use_corpus=use_corpus, train_camembert=False)


def _train_vision_model() -> dict:
    if not getattr(settings, "AI_USE_MICROSERVICES", True):
        return {"status": "skipped", "reason": "microservices désactivés"}

    import time

    from ai_gateway.clients.vision import VisionServiceClient
    from reports.vision_dataset import reset_exports_counter

    client = VisionServiceClient()
    start = client.train()
    if start.get("status") == "busy":
        return start

    deadline = time.time() + 7200
    last_status: dict = start
    while time.time() < deadline:
        time.sleep(30)
        last_status = client.train_status()
        state = last_status.get("status")
        if state in {"queued", "running"}:
            continue
        if state in {"completed", "error"}:
            if state == "completed":
                reset_exports_counter()
            return last_status

    return {"status": "timeout", "message": "Entraînement vision trop long", "last": last_status}


@shared_task(name="reports.tasks.train_ai_models")
def train_ai_models(model: str = "all"):
    """Réentraîne les modèles IA (prédiction, NLP, vision)."""
    from django.core.cache import cache

    valid = {"all", "prediction", "nlp", "vision"}
    if model not in valid:
        return {"error": f"model invalide : {model}"}

    started_at = timezone.now().isoformat()
    results: dict = {"started_at": started_at, "model": model, "status": "running"}
    targets = list(valid - {"all"}) if model == "all" else [model]

    cache.set(
        "ai:train:running",
        {
            "started_at": started_at,
            "model": model,
            "targets": targets,
            "current": targets[0] if targets else None,
        },
        7200,
    )

    try:
        if "prediction" in targets:
            cache.set(
                "ai:train:running",
                {**cache.get("ai:train:running", {}), "current": "prediction"},
                7200,
            )
            from prediction.tasks import train_prediction_model

            results["prediction"] = train_prediction_model()

        if "nlp" in targets:
            cache.set(
                "ai:train:running",
                {**cache.get("ai:train:running", {}), "current": "nlp"},
                7200,
            )
            try:
                results["nlp"] = _train_nlp_model()
            except Exception as exc:
                logger.exception("train nlp failed")
                results["nlp_error"] = str(exc)

        if "vision" in targets:
            cache.set(
                "ai:train:running",
                {**cache.get("ai:train:running", {}), "current": "vision"},
                7200,
            )
            try:
                results["vision"] = _train_vision_model()
            except Exception as exc:
                logger.exception("train vision failed")
                results["vision_error"] = str(exc)
    finally:
        results["finished_at"] = timezone.now().isoformat()
        results["status"] = "completed"
        cache.delete("ai:train:running")
        cache.set("ai:train:last_run", results, 86400)

    return results


@shared_task(name="reports.tasks.train_vision_model_weekly")
def train_vision_model_weekly():
    """Réentraînement vision hebdomadaire si activé et nouvelles images exportées."""
    from django.core.cache import cache

    from reports.models import ReportAISettings
    from reports.vision_dataset import EXPORTS_SINCE_TRAIN_KEY

    settings_obj = ReportAISettings.get_solo()
    if not settings_obj.auto_vision_retrain_weekly:
        return {"status": "skipped", "reason": "auto_vision_retrain_weekly désactivé"}

    exports = int(cache.get(EXPORTS_SINCE_TRAIN_KEY) or 0)
    if exports <= 0:
        return {"status": "skipped", "reason": "aucune nouvelle image depuis le dernier entraînement"}

    if cache.get("ai:train:running"):
        return {"status": "skipped", "reason": "entraînement déjà en cours"}

    return train_ai_models(model="vision")
