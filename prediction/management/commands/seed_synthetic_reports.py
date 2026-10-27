import random
import uuid
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone as dj_timezone

from locations.geo_validation import random_point_near_commune
from reports.models import Report
from reports.report_quality import SYNTHETIC_URL_PREFIX
from reports.synthetic_kinshasa import (
    RealisticKinshasaGenerator,
    load_marginals_from_prediction_csv,
)
from scrapping.services.geocoder import COMMUNE_CENTERS

# Ancien mode (10 phrases fixes) — conservé via --legacy
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


class Command(BaseCommand):
    help = (
        "Génère des signalements synthétiques pour l'entraînement ML. "
        "Par défaut : mode réaliste Kinshasa (templates variés, stats, déduplication). "
        "Utilisez --legacy pour l'ancien générateur."
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
            "--clear-only",
            action="store_true",
            help="Supprime uniquement les signalements synthétiques (aucune création).",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Graine aléatoire pour reproductibilité.",
        )
        parser.add_argument(
            "--legacy",
            action="store_true",
            help="Ancien générateur (10 phrases fixes, moins réaliste).",
        )
        parser.add_argument(
            "--min-distance-m",
            type=float,
            default=45.0,
            help="Distance minimale entre deux points synthétiques (mètres).",
        )

    def handle(self, *args, **options):
        if options["clear"] or options["clear_only"]:
            deleted, _ = Report.objects.filter(
                external_source_url__startswith=SYNTHETIC_URL_PREFIX
            ).delete()
            self.stdout.write(self.style.WARNING(f"Supprimé {deleted} signalement(s) synthétique(s)."))
            if options["clear_only"]:
                remaining = Report.objects.exclude(
                    external_source_url__startswith=SYNTHETIC_URL_PREFIX
                ).count()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Terminé. {remaining} signalement(s) non synthétique(s) conservé(s)."
                    )
                )
                return

        rng = random.Random(options["seed"])
        count = max(1, options["count"])

        if options["legacy"]:
            created = self._seed_legacy(rng, count)
            self._print_footer(created, mode="legacy")
            return

        marginals = load_marginals_from_prediction_csv()
        generator = RealisticKinshasaGenerator(
            rng,
            marginals=marginals,
            min_distance_m=options["min_distance_m"],
        )
        records, stats = generator.generate_many(count)

        if not records:
            self.stderr.write(self.style.ERROR("Aucun enregistrement généré (contraintes trop strictes)."))
            return

        batch: list[Report] = []
        created = 0
        for rec in records:
            created_at = rec.created_at
            if dj_timezone.is_naive(created_at):
                created_at = dj_timezone.make_aware(created_at)
            batch.append(
                Report(
                    description=rec.description,
                    location=rec.location,
                    latitude=rec.latitude,
                    longitude=rec.longitude,
                    degree=rec.degree,
                    status="V",
                    source="S",
                    incident_type="autre",
                    is_anonymous=True,
                    ai_processing_status="skipped",
                    external_source_url=f"{SYNTHETIC_URL_PREFIX}realistic/{uuid.uuid4()}",
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
                f"{created} signalement(s) synthétique(s) réalistes créé(s) (status=V, source=S)."
            )
        )
        self.stdout.write(
            f"Statistiques : {stats['unique_fingerprints']} empreintes uniques, "
            f"{stats['failed_retries']} échecs de tirage (doublons / trop proches)."
        )
        if marginals.hours:
            self.stdout.write(
                f"Bootstrap temporel : {len(marginals.hours)} heures et "
                f"{len(marginals.weekdays)} jours issus du CSV réel."
            )
        self._print_footer(created, mode="realistic")

    def _seed_legacy(self, rng: random.Random, count: int) -> int:
        communes = list(COMMUNE_CENTERS.items())
        degrees = [d for d, _ in DEGREE_WEIGHTS]
        weights = [w for _, w in DEGREE_WEIGHTS]
        created = 0
        now = dj_timezone.now()
        batch: list[Report] = []

        for _ in range(count):
            commune_key, _coords = rng.choice(communes)
            lat, lon = random_point_near_commune(rng, commune_key)
            commune_label = commune_key.title()
            template = rng.choice(INCIDENT_TEMPLATES)
            degree = rng.choices(degrees, weights=weights, k=1)[0]
            created_at = now - timedelta(hours=rng.randint(1, 720))

            batch.append(
                Report(
                    description=template,
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
        return created

    def _print_footer(self, created: int, mode: str) -> None:
        self.stdout.write(
            f"Mode : {mode}. Lancez ensuite :\n"
            "  docker compose exec web python manage.py export_reports_csv\n"
            "  docker compose exec web python manage.py train_prediction_model"
        )
