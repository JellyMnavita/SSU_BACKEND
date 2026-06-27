import csv
import os
import shutil
from datetime import datetime

from celery import shared_task
from django.conf import settings

CSV_PATH = os.path.join(settings.BASE_DIR, "prediction", "data", "data_reports.csv")
DEGREE_MAP = {"F": "faible", "M": "modéré", "E": "élevé"}


@shared_task(name="prediction.tasks.export_reports_to_csv")
def export_reports_to_csv():
    from reports.models import Report

    qs = Report.objects.filter(status="V").exclude(latitude=None).exclude(longitude=None)
    count = qs.count()

    if count == 0:
        return "Aucun signalement validé à exporter."

    if os.path.exists(CSV_PATH):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(CSV_PATH, CSV_PATH.replace(".csv", f"_backup_{timestamp}.csv"))

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "latitude_report", "longitude_report", "location_report",
            "degree_report", "description_report", "created_at",
        ])
        for report in qs.iterator():
            writer.writerow([
                report.latitude,
                report.longitude,
                (report.location or "Kinshasa").strip(),
                DEGREE_MAP.get(report.degree, "modéré"),
                (report.description or "").replace("\n", " ").strip(),
                report.created_at.strftime("%Y-%m-%d %H:%M:%S") if report.created_at else "",
            ])

    return f"{count} signalement(s) exporté(s) vers data_reports.csv"


@shared_task(name="prediction.tasks.train_prediction_model")
def train_prediction_model():
    """Exporte les signalements validés puis réentraîne via prediction-service."""
    export_msg = export_reports_to_csv()
    results = {"export": export_msg}

    try:
        from prediction.training import train_default_model

        results["train_local"] = train_default_model()
    except Exception as exc:
        results["train_local_error"] = str(exc)

    if getattr(settings, "AI_GATEWAY_ENABLED", True):
        try:
            from ai_gateway.clients.prediction import PredictionServiceClient

            client = PredictionServiceClient()
            results["train_microservice"] = client.train()
            results["reload_microservice"] = client.reload()
        except Exception as exc:
            results["train_microservice_error"] = str(exc)

    return results
