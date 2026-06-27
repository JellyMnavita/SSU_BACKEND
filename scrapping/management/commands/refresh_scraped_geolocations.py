"""Recalcule la géolocalisation des signalements source=S (ingestion actualités)."""

from django.core.management.base import BaseCommand
from django.db import transaction

from reports.models import Report, ScrapedReport
from scrapping.services.geocoder import geocode_kinshasa, clear_place_index_cache


class Command(BaseCommand):
    help = "Met à jour latitude/longitude/location des signalements système (source=S)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--report-id",
            type=int,
            help="Recalculer un seul signalement (ex. 327).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Affiche les changements sans écrire en base.",
        )

    def handle(self, *args, **options):
        clear_place_index_cache()
        qs = Report.objects.filter(source="S").select_related("quartier")
        if options.get("report_id"):
            qs = qs.filter(pk=options["report_id"])

        updated = 0
        for report in qs.iterator():
            scraped = None
            try:
                scraped = report.scraped_article
            except ScrapedReport.DoesNotExist:
                pass
            text = report.description or ""
            if scraped:
                text = f"{scraped.title}\n{scraped.content or report.description}"

            geo = geocode_kinshasa(text)
            if not geo:
                self.stdout.write(self.style.WARNING(f"#{report.id} — géoloc impossible, ignoré."))
                continue

            old = (report.latitude, report.longitude, report.location)
            new = (geo["latitude"], geo["longitude"], geo["location"])
            if old == new and report.quartier_id == getattr(geo.get("quartier"), "pk", None):
                continue

            self.stdout.write(
                f"#{report.id}: {report.location!r} ({report.latitude}, {report.longitude}) "
                f"→ {geo['location']!r} ({geo['latitude']}, {geo['longitude']})"
            )
            if options["dry_run"]:
                updated += 1
                continue

            with transaction.atomic():
                report.latitude = geo["latitude"]
                report.longitude = geo["longitude"]
                report.location = geo["location"]
                if geo.get("quartier"):
                    report.quartier = geo["quartier"]
                report.save(update_fields=["latitude", "longitude", "location", "quartier"])
                if scraped:
                    scraped.latitude = geo["latitude"]
                    scraped.longitude = geo["longitude"]
                    scraped.location_label = geo["location"]
                    scraped.save(update_fields=["latitude", "longitude", "location_label"])
            updated += 1

        self.stdout.write(self.style.SUCCESS(f"{updated} signalement(s) mis à jour."))
