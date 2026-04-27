import csv
import os
import shutil
from datetime import datetime

from django.core.management.base import BaseCommand
from django.conf import settings

from reports.models import Report

CSV_PATH = os.path.join(settings.BASE_DIR, "prediction", "data", "data_reports.csv")

DEGREE_MAP = {"F": "faible", "M": "modéré", "E": "élevé"}


class Command(BaseCommand):
    help = "Exporte les signalements validés de la BDD vers prediction/data/data_reports.csv."

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Inclure tous les statuts (P, V, R). Par défaut : uniquement les validés (V).",
        )
        parser.add_argument(
            "--no-backup",
            action="store_true",
            help="Ne pas créer de backup du CSV existant avant l'export.",
        )

    def handle(self, *args, **options):
        # Backup du CSV existant
        if not options["no_backup"] and os.path.exists(CSV_PATH):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = CSV_PATH.replace(".csv", f"_backup_{timestamp}.csv")
            shutil.copy2(CSV_PATH, backup_path)
            self.stdout.write(f"Backup créé : {backup_path}")

        # Filtrage des signalements
        qs = Report.objects.all()
        if not options["all"]:
            qs = qs.filter(status="V")

        # Exclure les entrées sans coordonnées valides
        qs = qs.exclude(latitude=None).exclude(longitude=None)

        count = qs.count()
        if count == 0:
            self.stdout.write(self.style.WARNING("Aucun signalement à exporter."))
            return

        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "latitude_report",
                "longitude_report",
                "location_report",
                "degree_report",
                "description_report",
                "created_at",
            ])

            for report in qs.iterator():
                degree = DEGREE_MAP.get(report.degree, "modéré")
                location = (report.location or "Kinshasa").strip()
                description = (report.description or "").replace("\n", " ").strip()
                created_at = report.created_at.strftime("%Y-%m-%d %H:%M:%S") if report.created_at else ""

                writer.writerow([
                    report.latitude,
                    report.longitude,
                    location,
                    degree,
                    description,
                    created_at,
                ])

        self.stdout.write(
            self.style.SUCCESS(
                f"Export terminé : {count} signalement(s) exporté(s) vers {CSV_PATH}"
            )
        )
