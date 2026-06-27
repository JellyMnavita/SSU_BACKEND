"""
Exporte la photo d'un signalement vers vision_data/labeled/ (réentraînement).

Usage :
  docker compose exec web python manage.py export_vision_feedback --report-id 893 --label arme
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from reports.models import Report
from reports.vision_feedback import apply_vision_label_correction


class Command(BaseCommand):
    help = "Ajoute une image de signalement au dataset vision (labeled/) pour réentraînement."

    def add_arguments(self, parser):
        parser.add_argument("--report-id", type=int, required=True)
        parser.add_argument("--label", type=str, required=True)

    def handle(self, *args, **options):
        report = Report.objects.filter(pk=options["report_id"]).first()
        if not report:
            raise CommandError(f"Signalement {options['report_id']} introuvable")
        try:
            result = apply_vision_label_correction(report, options["label"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"Exporté → {result.get('path')} (retrain_queued={result.get('retrain_queued')})"
            )
        )
