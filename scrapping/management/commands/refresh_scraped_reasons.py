"""Recalcule les motifs de rejet des articles déjà en base."""

from django.core.management.base import BaseCommand

from reports.models import ScrapedReport
from scrapping.services.security_filter import (
    explain_geo_rejection,
    explain_security_rejection,
    is_security_related,
    mentions_kinshasa,
)
from scrapping.services.geocoder import geocode_kinshasa


class Command(BaseCommand):
    help = "Met à jour les motifs de rejet (reject_reason) des ScrapedReport status=R."

    def handle(self, *args, **options):
        updated = 0
        for scraped in ScrapedReport.objects.filter(status="R"):
            text = f"{scraped.title}\n{scraped.content}"
            if not is_security_related(text):
                reason = explain_security_rejection(text)
            elif not geocode_kinshasa(text) and not mentions_kinshasa(text):
                reason = explain_geo_rejection(text)
            else:
                reason = scraped.reject_reason or "Rejet historique — relancer l'ingestion."

            if scraped.reject_reason != reason:
                scraped.reject_reason = reason
                scraped.save(update_fields=["reject_reason"])
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"{updated} motif(s) mis à jour."))
