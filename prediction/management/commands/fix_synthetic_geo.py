from django.core.management.base import BaseCommand

from locations.geo_validation import is_on_water_zone, random_point_near_commune
from reports.models import Report
from reports.report_quality import SYNTHETIC_URL_PREFIX
from scrapping.services.geocoder import COMMUNE_CENTERS


class Command(BaseCommand):
    help = "Repositionne les signalements synthétiques tombés sur le fleuve."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        import random

        rng = random.Random(7)
        qs = Report.objects.filter(external_source_url__startswith=SYNTHETIC_URL_PREFIX)
        fixed = 0

        for report in qs.iterator():
            if not is_on_water_zone(report.latitude, report.longitude):
                continue

            commune_key = None
            location = (report.location or "").lower()
            for key in COMMUNE_CENTERS:
                if key in location:
                    commune_key = key
                    break
            if not commune_key:
                commune_key = rng.choice(list(COMMUNE_CENTERS.keys()))

            lat, lon = random_point_near_commune(rng, commune_key)
            label = f"#{report.id}"
            if options["dry_run"]:
                self.stdout.write(f"[DRY-RUN] {label} → {lat:.5f}, {lon:.5f}")
            else:
                report.latitude = lat
                report.longitude = lon
                report.save(update_fields=["latitude", "longitude"])
                self.stdout.write(f"Corrigé {label} → {lat:.5f}, {lon:.5f}")
            fixed += 1

        self.stdout.write(self.style.SUCCESS(f"Terminé — {fixed} signalement(s) repositionné(s)."))
