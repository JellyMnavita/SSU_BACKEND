"""Export des signalements SSU vers le corpus NLP (Phase 2)."""

from __future__ import annotations

import csv
import os
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db.models import F

from reports.models import Report

NLP_LABELS = frozenset(
    {"violence", "vol", "kidnapping", "agression", "vandalisme", "autre"}
)
DEGREE_TO_NLP_LABEL = {"F": "autre", "M": "vol", "E": "violence"}


def default_nlp_data_dir() -> Path:
    if env := os.environ.get("NLP_DATA_DIR"):
        return Path(env)
    ssu_backend_root = Path(__file__).resolve().parents[3]
    repo_candidate = ssu_backend_root.parent / "nlp_data"
    if repo_candidate.is_dir():
        return repo_candidate
    return ssu_backend_root / "nlp_data"


def resolve_nlp_label(report: Report) -> str:
    from ai_gateway.services.content_filters import looks_non_security_news

    if report.status == "R":
        return "autre"

    text = (report.description or "").strip()
    if looks_non_security_news(text):
        return "autre"

    label = (report.ai_incident_type or report.incident_type or "").strip().lower()
    if label == "accident":
        return "agression"
    if label in NLP_LABELS:
        return label
    return DEGREE_TO_NLP_LABEL.get(report.degree, "autre")


class Command(BaseCommand):
    help = "Exporte les signalements SSU vers nlp_data/raw/ssu_reports.csv."

    def add_arguments(self, parser):
        default_out = default_nlp_data_dir() / "raw" / "ssu_reports.csv"
        parser.add_argument(
            "--output",
            type=str,
            default=str(default_out),
            help="Fichier CSV de sortie",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=2000,
            help="Nombre max de signalements exportés",
        )
        parser.add_argument(
            "--all-statuses",
            action="store_true",
            help="Inclure P/V/R (défaut : V, R et corrections humaines)",
        )

    def handle(self, *args, **options):
        output = Path(options["output"])
        output.parent.mkdir(parents=True, exist_ok=True)
        limit = int(options["limit"])

        rows: list[dict] = []
        seen: set[int] = set()

        def add_report(report: Report, source: str) -> None:
            if report.id in seen or len(rows) >= limit:
                return
            text = (report.description or "").strip().replace("\n", " ")
            if len(text) < 15:
                return
            label = resolve_nlp_label(report)
            rows.append(
                {
                    "text": text[:2000],
                    "label": label,
                    "source": source,
                    "report_id": report.id,
                    "status": report.status,
                }
            )
            seen.add(report.id)

        if not options["all_statuses"]:
            overrides = (
                Report.objects.filter(status__in=["V", "R"])
                .exclude(ai_moderation_recommendation="")
                .exclude(description="")
                .exclude(ai_moderation_recommendation=F("status"))
                .order_by("-created_at")[: max(limit // 4, 50)]
            )
            for report in overrides:
                add_report(report, "ssu_human_override")

            for report in (
                Report.objects.filter(status="V")
                .exclude(description="")
                .order_by("-created_at")[: max(limit // 2, 100)]
            ):
                add_report(report, "ssu_validated")

            for report in (
                Report.objects.filter(status="R")
                .exclude(description="")
                .order_by("-created_at")[: max(limit // 4, 80)]
            ):
                add_report(report, "ssu_rejected")
        else:
            for report in Report.objects.exclude(description="").order_by("-created_at")[:limit]:
                add_report(report, "ssu_all")

        with open(output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["text", "label", "source", "report_id", "status"],
            )
            writer.writeheader()
            writer.writerows(rows)

        self.stdout.write(
            self.style.SUCCESS(
                f"Export NLP : {len(rows)} ligne(s) → {output}"
            )
        )
