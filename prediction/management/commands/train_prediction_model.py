from django.conf import settings
from django.core.management.base import BaseCommand

from prediction.training import train_default_model


class Command(BaseCommand):
    help = "Réentraîne le modèle de prédiction sur prediction/data/data_reports.csv."

    def handle(self, *args, **options):
        try:
            result = train_default_model()
        except Exception as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            return

        if getattr(settings, "AI_GATEWAY_ENABLED", True):
            try:
                from ai_gateway.clients.prediction import PredictionServiceClient

                client = PredictionServiceClient()
                client.reload()
                self.stdout.write("Cache prediction-service vidé.")
            except Exception as exc:
                self.stderr.write(self.style.WARNING(f"Reload microservice: {exc}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Modèle entraîné ({result['algorithm']}) — "
                f"{result['samples_used']} échantillon(s), "
                f"répartition {result['class_distribution']}"
            )
        )
        if result.get("selection_reason"):
            self.stdout.write(result["selection_reason"])
        if result.get("gold_metrics"):
            gm = result["gold_metrics"]
            self.stdout.write(
                f"Gold eval — accuracy={gm.get('accuracy', 0):.3f}, "
                f"f1_macro={gm.get('f1_macro', 0):.3f}"
            )
