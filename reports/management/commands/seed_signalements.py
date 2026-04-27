import base64
import csv
import os
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from locations.models import Quartier
from reports.models import Report

_MIN_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

CSV_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "prediction", "data", "data_reports.csv"
)

DEGREE_MAP = {
    "0": "F", "1": "M", "2": "E",
    "F": "F", "M": "M", "E": "E",
    "Faible": "F", "Moyen": "M", "Elevé": "E", "Eleve": "E",
}

STATUS_MAP = {
    "P": "P", "V": "V", "R": "R",
    "Pending": "P", "Validated": "V", "Rejected": "R",
}


class Command(BaseCommand):
    help = "Importe les signalements depuis data_reports.csv dans la base de données."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Supprime tous les signalements source=S avant d'importer.",
        )
        parser.add_argument(
            "--csv",
            type=str,
            default=CSV_PATH,
            help="Chemin vers le fichier CSV (défaut : prediction/data/data_reports.csv).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        csv_path = options["csv"]

        if not os.path.exists(csv_path):
            self.stderr.write(self.style.ERROR(f"Fichier CSV introuvable : {csv_path}"))
            return

        if options["clear"]:
            deleted, _ = Report.objects.filter(source="S").delete()
            self.stdout.write(self.style.WARNING(f"Supprimé {deleted} signalement(s) source=S."))

        quartiers = {q.nom.lower(): q for q in Quartier.objects.all()}

        created = 0
        skipped = 0

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            # Normalise les noms de colonnes (strip espaces)
            reader.fieldnames = [h.strip() for h in reader.fieldnames]

            for i, row in enumerate(reader):
                try:
                    lat = float(row.get("latitude_report") or row.get("latitude") or 0)
                    lon = float(row.get("longitude_report") or row.get("longitude") or 0)
                except (ValueError, TypeError):
                    skipped += 1
                    continue

                if lat == 0 and lon == 0:
                    skipped += 1
                    continue

                raw_degree = str(row.get("degree") or row.get("degree_report") or "M").strip()
                degree = DEGREE_MAP.get(raw_degree, "M")

                raw_status = str(row.get("status") or "P").strip()
                status = STATUS_MAP.get(raw_status, "P")

                description = str(row.get("description") or row.get("description_report") or f"Signalement #{i+1}").strip()[:500]
                location = str(row.get("location") or row.get("adresse") or "Kinshasa").strip()[:200]

                # Quartier optionnel
                quartier = None
                raw_quartier = str(row.get("quartier") or "").strip().lower()
                if raw_quartier:
                    quartier = quartiers.get(raw_quartier)

                picture = ContentFile(BytesIO(_MIN_PNG).read(), name=f"csv_seed_{i}.png")

                Report.objects.create(
                    description=description,
                    location=location,
                    longitude=lon,
                    latitude=lat,
                    degree=degree,
                    picture=picture,
                    status=status,
                    source="S",
                    user=None,
                    citizen=None,
                    quartier=quartier,
                )
                created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Import terminé : {created} signalement(s) créé(s), {skipped} ligne(s) ignorée(s)."
            )
        )
