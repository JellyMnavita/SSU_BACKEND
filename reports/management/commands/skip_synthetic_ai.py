from django.core.management.base import BaseCommand
from django.utils import timezone

from reports.models import Report
from reports.report_quality import SYNTHETIC_URL_PREFIX


class Command(BaseCommand):
    help = "Marque les signalements synthétiques d'entraînement comme ignorés par l'IA."

    def handle(self, *args, **options):
        now = timezone.now()
        updated = Report.objects.filter(
            external_source_url__startswith=SYNTHETIC_URL_PREFIX,
            ai_processing_status__in=["pending", "processing"],
        ).update(ai_processing_status="skipped", ai_processed_at=now)
        self.stdout.write(self.style.SUCCESS(f"{updated} signalement(s) synthétique(s) passés en « ignoré IA »."))
