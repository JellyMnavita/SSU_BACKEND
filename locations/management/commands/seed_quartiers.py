from django.core.management.base import BaseCommand
from django.db import transaction

from locations.models import Commune, Quartier


class Command(BaseCommand):
    help = "Seed minimal quartiers for each commune (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--name",
            default="Non spécifié",
            help="Nom du quartier créé par défaut pour chaque commune sans quartiers.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Créer le quartier même si la commune a déjà des quartiers (évite normalement).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        default_name: str = options["name"]
        force: bool = options["force"]

        communes = list(Commune.objects.all())
        if not communes:
            self.stdout.write(self.style.WARNING("Aucune commune trouvée. Rien à seeder."))
            return

        created = 0
        skipped = 0

        for commune in communes:
            has_any = Quartier.objects.filter(commune=commune).exists()
            if has_any and not force:
                skipped += 1
                continue

            # Idempotent: do not duplicate same (commune, nom)
            obj, was_created = Quartier.objects.get_or_create(
                commune=commune,
                nom=default_name,
                defaults={
                    # limites_gps est requis dans le modèle
                    "limites_gps": "[]",
                },
            )
            if was_created:
                created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed terminé. Quartiers créés: {created}. Communes ignorées: {skipped}."
            )
        )

