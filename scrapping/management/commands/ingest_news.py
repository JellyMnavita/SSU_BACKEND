from django.core.management.base import BaseCommand

from scrapping.services.ingest import run_news_ingest


class Command(BaseCommand):
    help = "Scrape les actualités sécurité et crée des signalements source=S (Kinshasa)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--max",
            type=int,
            default=50,
            help="Nombre max d'articles à traiter par exécution.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Lancer même si auto_ingest_news est désactivé.",
        )

    def handle(self, *args, **options):
        stats = run_news_ingest(
            max_articles=options["max"],
            force=options["force"],
        )
        self.stdout.write(self.style.SUCCESS(str(stats)))
