"""Répare les alertes SOS rejetées ou en attente avant la validation système automatique."""

from django.core.management.base import BaseCommand

from reports.models import Report
from safety.sos_report import finalize_sos_report


class Command(BaseCommand):
    help = "Valide automatiquement les signalements SOS (source=O) encore en attente ou rejetés."

    def handle(self, *args, **options):
        qs = Report.objects.filter(source="O").exclude(status="V")
        count = qs.count()
        for report in qs.iterator():
            finalize_sos_report(report)
        self.stdout.write(self.style.SUCCESS(f"{count} alerte(s) SOS corrigée(s)."))
