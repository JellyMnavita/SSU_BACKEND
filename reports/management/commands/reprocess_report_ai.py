"""Relance l'analyse IA sur un signalement existant."""

from django.core.management.base import BaseCommand

from reports.models import Report
from reports.tasks import process_report_ai


class Command(BaseCommand):
    help = "Relance process_report_ai sur un ou plusieurs signalements."

    def add_arguments(self, parser):
        parser.add_argument("--report-id", type=int, action="append", dest="report_ids")
        parser.add_argument("--all-scraped", action="store_true", help="Tous les source=S")

    def handle(self, *args, **options):
        report_ids = options.get("report_ids") or []
        if options.get("all_scraped"):
            report_ids.extend(
                Report.objects.filter(source="S").values_list("id", flat=True)
            )
        if not report_ids:
            self.stderr.write("Indiquez --report-id ou --all-scraped")
            return

        for rid in sorted(set(report_ids)):
            report = Report.objects.filter(pk=rid).first()
            if not report:
                self.stderr.write(f"Signalement {rid} introuvable")
                continue
            report.ai_processing_status = "pending"
            report.save(update_fields=["ai_processing_status"])
            process_report_ai.delay(rid)
            self.stdout.write(f"IA relancée pour RPT-{rid}")
