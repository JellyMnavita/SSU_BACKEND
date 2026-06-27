from django.core.management.base import BaseCommand

from reports.cache_utils import invalidate_reports_list_cache
from reports.models import Report
from reports.report_quality import get_rejection_reason, is_synthetic_training_report


class Command(BaseCommand):
    help = (
        "Rejette les signalements validés (V) de mauvaise qualité : blagues, "
        "actualités hors sécurité, GPS sur le fleuve ou incohérents avec le lieu."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Affiche les rejets sans modifier la base.",
        )
        parser.add_argument(
            "--include-scraped",
            action="store_true",
            help="Inclure aussi les signalements source=S (scraping).",
        )

    def handle(self, *args, **options):
        qs = Report.objects.filter(status="V").select_related("quartier", "quartier__commune")
        if not options["include_scraped"]:
            qs = qs.exclude(source="S")

        rejected = 0
        kept = 0

        for report in qs.iterator():
            if is_synthetic_training_report(report):
                kept += 1
                continue

            reason = get_rejection_reason(report)
            if not reason:
                kept += 1
                continue

            rejected += 1
            label = f"#{report.id} «{(report.description or '')[:60]}…»"
            if options["dry_run"]:
                self.stdout.write(self.style.WARNING(f"[DRY-RUN] Rejet {label} — {reason}"))
                continue

            report.status = "R"
            report.ai_moderation_reasons = (report.ai_moderation_reasons or []) + [
                f"Nettoyage auto : {reason}"
            ]
            report.save(update_fields=["status", "ai_moderation_reasons"])
            self.stdout.write(self.style.WARNING(f"Rejeté {label} — {reason}"))

        if not options["dry_run"] and rejected:
            invalidate_reports_list_cache()

        self.stdout.write(
            self.style.SUCCESS(
                f"Terminé — conservés: {kept}, rejetés: {rejected}"
                + (" (simulation)" if options["dry_run"] else "")
            )
        )
