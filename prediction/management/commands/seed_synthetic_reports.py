import random
import uuid
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from locations.geo_validation import is_on_water_zone, random_point_near_commune
from reports.models import Report
from reports.report_quality import SYNTHETIC_URL_PREFIX
from scrapping.services.geocoder import COMMUNE_CENTERS

INCIDENT_TEMPLATES = [
    "Vol à la tire signalé près d'un marché.",
    "Groupe suspect observé en soirée.",
    "Agression verbale puis fuite des auteurs.",
    "Cambriolage tenté, porte forcée.",
    "Accident de circulation avec dégâts matériels.",
    "Bagarre entre passants, situation calmée.",
    "Vandalisme sur véhicule stationné.",
    "Personnes armées aperçues, vigilance recommandée.",
    "Tapage nocturne et attroupement.",
    "Pickpocket signalé dans un bus.",
]

DEGREE_WEIGHTS = [("F", 0.60), ("M", 0.25), ("E", 0.15)]


def _random_point_near_commune(rng, commune_key: str) -> tuple[float, float]:
    return random_point_near_commune(rng, commune_key)


class Command(BaseCommand):
    help = (
        "Génère des signalements synthétiques anonymes répartis sur Kinshasa "
        "pour enrichir l'entraînement du modèle de prédiction."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=20,
            help="Nombre de signalements à créer (défaut : 20).",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Supprime les signalements synthétiques existants avant création.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Graine aléatoire pour reproductibilité.",
        )

    def handle(self, *args, **options):
        rng = random.Random(options["seed"])
        count = max(1, options["count"])

        if options["clear"]:
            deleted, _ = Report.objects.filter(
                external_source_url__startswith=SYNTHETIC_URL_PREFIX
            ).delete()
            self.stdout.write(self.style.WARNING(f"Supprimé {deleted} signalement(s) synthétique(s)."))

        communes = list(COMMUNE_CENTERS.items())
        degrees = [d for d, _ in DEGREE_WEIGHTS]
        weights = [w for _, w in DEGREE_WEIGHTS]

        created = 0
        now = timezone.now()
        batch: list[Report] = []

        for index in range(count):
            commune_key, _coords = rng.choice(communes)
            lat, lon = _random_point_near_commune(rng, commune_key)
            commune_label = commune_key.title()
            template = rng.choice(INCIDENT_TEMPLATES)
            degree = rng.choices(degrees, weights=weights, k=1)[0]
            created_at = now - timedelta(hours=rng.randint(1, 720))

            batch.append(
                Report(
                    description=f"{template}",
                    location=f"{commune_label}, Kinshasa",
                    latitude=lat,
                    longitude=lon,
                    degree=degree,
                    status="V",
                    source="S",
                    incident_type="autre",
                    is_anonymous=True,
                    ai_processing_status="skipped",
                    external_source_url=f"{SYNTHETIC_URL_PREFIX}{uuid.uuid4()}",
                    created_at=created_at,
                )
            )

            if len(batch) >= 100:
                Report.objects.bulk_create(batch)
                created += len(batch)
                batch.clear()

        if batch:
            Report.objects.bulk_create(batch)
            created += len(batch)

        self.stdout.write(
            self.style.SUCCESS(
                f"{created} signalement(s) synthétique(s) créé(s) (status=V, source=S)."
            )
        )
        self.stdout.write(
            "Lancez ensuite : python manage.py export_reports_csv && "
            "python manage.py train_prediction_model (ou tâche Celery)."
        )
