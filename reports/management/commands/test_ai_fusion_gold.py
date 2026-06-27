"""
Test fusion NLP + Vision sur images gold_eval (hors train/val/test).

Usage (stack Docker démarrée) :
  docker compose exec web python manage.py test_ai_fusion_gold --limit 12
  docker compose exec web python manage.py test_ai_fusion_gold --image labeled/incendie/xxx.jpg --label incendie
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from ai_gateway.clients import NLPServiceClient, VisionServiceClient
from ai_gateway.clients.base import AIServiceError
from ai_gateway.services.fusion import compute_fusion

# Descriptions types par classe vision (pour tester la fusion)
SAMPLE_DESCRIPTIONS = {
    "arme": "Homme armé dans la rue, population en panique à Kinshasa.",
    "foule": "Foule dense et manifestation sur l'avenue, tensions observées.",
    "vehicule_suspect": "Véhicule suspect stationné depuis longtemps, comportement anormal.",
    "accident": "Accident de la route, plusieurs véhicules impliqués, blessés.",
    "incendie": "Incendie et fumée noire, feu visible sur un bâtiment.",
    "autre": "Situation calme dans le quartier, circulation normale.",
}


def _vision_data_dir() -> Path:
    return Path(os.environ.get("VISION_DATA_DIR", Path(settings.BASE_DIR).parent / "vision_data"))


def _repo_root() -> Path:
    return Path(settings.BASE_DIR).parent


def _resolve_image_path(rel: str) -> Path | None:
    """Chemins gold_eval : relatifs à vision_data/ (ex. labeled/arme/foo.jpg)."""
    raw = Path(rel)
    if raw.is_absolute() and raw.is_file():
        return raw

    vision_root = _vision_data_dir()
    repo_root = _repo_root()
    candidates = [
        vision_root / rel,
        repo_root / rel,
        repo_root / "vision_data" / rel,
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def _load_gold_rows(limit: int) -> tuple[list[dict], Path]:
    gold_csv = _vision_data_dir() / "gold_eval" / "gold_eval.csv"
    if not gold_csv.is_file():
        return [], gold_csv
    rows: list[dict] = []
    with gold_csv.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(row)
            if len(rows) >= limit:
                break
    return rows, gold_csv


class Command(BaseCommand):
    help = "Teste NLP + Vision + fusion sur images gold_eval ou un fichier local."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=12,
            help="Nombre d'images gold_eval à tester",
        )
        parser.add_argument(
            "--image",
            type=str,
            default="",
            help="Chemin image (relatif à vision_data/, ex. labeled/incendie/foo.jpg)",
        )
        parser.add_argument(
            "--description",
            type=str,
            default="",
            help="Texte NLP pour --image (sinon déduit de la classe)",
        )
        parser.add_argument(
            "--label",
            type=str,
            default="",
            help="Classe attendue pour --image",
        )

    def handle(self, *args, **options):
        vision_root = _vision_data_dir()
        nlp_client = NLPServiceClient()
        vision_client = VisionServiceClient()

        samples: list[tuple[str, str, str]] = []
        if options.get("image"):
            rel = options["image"]
            label = options.get("label") or "?"
            desc = options.get("description") or SAMPLE_DESCRIPTIONS.get(label, "Signalement à Kinshasa.")
            samples.append((rel, label, desc))
        else:
            rows, gold_csv = _load_gold_rows(options["limit"])
            if not rows:
                self.stderr.write(
                    f"Aucun échantillon gold_eval.\n"
                    f"  CSV attendu : {gold_csv}\n"
                    f"  VISION_DATA_DIR : {vision_root} "
                    f"({'existe' if vision_root.is_dir() else 'introuvable'})\n"
                    f"Montez ./vision_data dans le conteneur web ou définissez VISION_DATA_DIR."
                )
                return
            for row in rows:
                rel = row.get("path", "")
                label = row.get("label", "?")
                desc = SAMPLE_DESCRIPTIONS.get(label, "Signalement sécurité à Kinshasa.")
                samples.append((rel, label, desc))

        self.stdout.write(self.style.MIGRATE_HEADING("=== Test fusion NLP + Vision ==="))
        self.stdout.write(f"VISION_DATA_DIR : {vision_root}\n")

        ok = 0
        tested = 0
        for rel, true_label, description in samples:
            image_path = _resolve_image_path(rel)
            if image_path is None:
                self.stderr.write(f"Image introuvable : {rel} (cherché sous {vision_root})")
                continue

            tested += 1
            image_bytes = image_path.read_bytes()
            filename = image_path.name

            try:
                nlp = nlp_client.classify_text(description)
            except AIServiceError as exc:
                self.stderr.write(f"NLP échec {rel}: {exc}")
                continue

            try:
                vision = vision_client.analyze_image(image_bytes, filename)
            except AIServiceError as exc:
                self.stderr.write(f"Vision échec {rel}: {exc}")
                continue

            fusion = compute_fusion(description, nlp, vision)
            top_vision = (vision.get("detected_objects") or [{}])[0]
            pred_label = top_vision.get("label", "?")
            pred_conf = top_vision.get("confidence", 0)
            match = "OK" if pred_label == true_label else "KO"

            if match == "OK":
                ok += 1

            self.stdout.write(
                f"\n[{match}] {rel}\n"
                f"  Vérité      : {true_label}\n"
                f"  Vision      : {pred_label} ({pred_conf:.0%}) — {vision.get('model_used')}\n"
                f"  NLP         : {nlp.get('incident_type')} ({nlp.get('confidence', 0):.0%})\n"
                f"  Fusion      : score={fusion.get('fusion_score')} "
                f"degré={fusion.get('ai_recommended_degree')}\n"
                f"  Description : {description[:80]}…"
            )

        if tested:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nRésumé vision : {ok}/{tested} prédictions correctes (top-1)"
                )
            )
