from django.core.management.base import BaseCommand
from django.db import transaction

from locations.models import Commune, Quartier

# Quartiers courants par commune (domicile citoyen — idempotent via get_or_create).
KNOWN_QUARTIERS_BY_COMMUNE: dict[str, list[str]] = {
    "Bandalungwa": ["Bandal", "Mupila", "Kimbwala"],
    "Barumbu": ["Barumbu", "Fleuve"],
    "Bumbu": ["Bumbu", "Sele"],
    "Gombe": ["Centre-ville", "Socimat"],
    "Kalamu": ["Kalamu", "Kampemba", "Matonge"],
    "Kasa-Vubu": ["Kasa-Vubu", "Kalamu", "Lubudi"],
    "Kimbanseke": ["Kimbanseke", "Mobutu", "Mikondo"],
    "Kinshasa": ["Gare Centrale", "Kinshasa"],
    "Kintambo": ["Kintambo", "Magasin", "Mabondo"],
    "Kisenso": ["Kisenso", "Limete-Funa"],
    "Lemba": ["Lemba", "Righini", "Université"],
    "Limete": ["Limete", "Kingabwa", "Industriel"],
    "Lingwala": ["Lingwala", "Ngiri-Ngiri"],
    "Makala": ["Makala", "Mbanza", "Camp Luka"],
    "Maluku": ["Menkao", "Menkao II", "Kinkole", "Mabuku", "Bibwa"],
    "Masina": ["Masina", "Sans Fil", "Quartier 6", "Pilote"],
    "Matete": ["Matete", "Salongo", "Kinkole"],
    "Mont-Ngafula": ["Mont-Ngafula", "Mbanza-Ngungu", "Lemba-Salongo"],
    "Ndjili": ["Ndjili", "Ndjili Brasserie", "Masangambila"],
    "Ngaba": ["Ngaba", "Mfidi", "Kimbwala"],
    "Ngaliema": [
        "Binza",
        "Delvaux",
        "Mont Fleuri",
        "Victoire",
        "UPN",
        "Joli Parc",
        "Golf",
        "Ma Campagne",
    ],
    "Ngiri-Ngiri": ["Ngiri-Ngiri", "Lemba-Salongo"],
    "Nsele": ["Mikondo", "Pembenza", "Nsele Centre"],
    "Selembao": ["Selembao", "Mbanza-Lemba"],
}


class Command(BaseCommand):
    help = "Seed quartiers for each commune (placeholder + noms connus, idempotent)."

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
        parser.add_argument(
            "--skip-known",
            action="store_true",
            help="Ne pas ajouter les quartiers connus (Menkao, Binza, etc.).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        default_name: str = options["name"]
        force: bool = options["force"]
        skip_known: bool = options["skip_known"]

        communes = list(Commune.objects.all())
        if not communes:
            self.stdout.write(self.style.WARNING("Aucune commune trouvée. Rien à seeder."))
            return

        created = 0
        skipped = 0
        known_created = 0

        for commune in communes:
            has_any = Quartier.objects.filter(commune=commune).exists()
            if has_any and not force:
                skipped += 1
            else:
                _, was_created = Quartier.objects.get_or_create(
                    commune=commune,
                    nom=default_name,
                    defaults={"limites_gps": "[]"},
                )
                if was_created:
                    created += 1

            if skip_known:
                continue

            for quartier_name in KNOWN_QUARTIERS_BY_COMMUNE.get(commune.nom, []):
                _, was_created = Quartier.objects.get_or_create(
                    commune=commune,
                    nom=quartier_name,
                    defaults={"limites_gps": "[]"},
                )
                if was_created:
                    known_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Seed terminé. "
                f"Placeholders créés: {created}. "
                f"Quartiers connus ajoutés: {known_created}. "
                f"Communes ignorées (placeholder): {skipped}."
            )
        )
