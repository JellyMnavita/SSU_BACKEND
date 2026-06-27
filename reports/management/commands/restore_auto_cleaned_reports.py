from django.core.management.base import BaseCommand

from reports.cache_utils import invalidate_reports_list_cache
from reports.models import Report


class Command(BaseCommand):
    help = "Restaure les signalements rejetés par le nettoyage auto (faux positifs GPS/eau)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ids",
            type=str,
            default="",
            help="IDs séparés par des virgules (ex. 373). Vide = tous les rejets nettoyage auto.",
        )
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        qs = Report.objects.filter(status="R")
        if options["ids"].strip():
            ids = [int(x.strip()) for x in options["ids"].split(",") if x.strip()]
            qs = qs.filter(pk__in=ids)
        else:
            qs = qs.filter(ai_moderation_reasons__icontains="Nettoyage auto")

        restored = 0
        for report in qs.iterator():
            reasons = report.ai_moderation_reasons or []
            if not any("Nettoyage auto" in str(r) for r in reasons):
                continue
            label = f"#{report.id}"
            if options["dry_run"]:
                self.stdout.write(self.style.WARNING(f"[DRY-RUN] Restauration {label} → V"))
            else:
                report.status = "V"
                report.save(update_fields=["status"])
                self.stdout.write(self.style.SUCCESS(f"Restauré {label} → V"))
            restored += 1

        if not options["dry_run"] and restored:
            invalidate_reports_list_cache()

        self.stdout.write(self.style.SUCCESS(f"Terminé — {restored} signalement(s)."))
