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
            micro = client.train()
            results["train_microservice"] = micro
            results["reload_microservice"] = client.reload()
            # Aligne active_model.json côté Django sur le modèle servi par le micro
            # (évite badge / raison désynchronisés si volumes web ≠ celery).
            try:
                import json
                from datetime import datetime, timezone
                from pathlib import Path

                active_path = Path(settings.BASE_DIR) / "prediction" / "model" / "active_model.json"
                active_path.parent.mkdir(parents=True, exist_ok=True)
                local = results.get("train_local") or {}
                algo = micro.get("algorithm") or local.get("algorithm")
                comparison = micro.get("comparison") or local.get("comparison") or {}
                payload = {
                    "algorithm": algo,
                    "best_params": micro.get("best_params") or local.get("best_params") or {},
                    "trained_at": datetime.now(timezone.utc).isoformat(),
                    "f1_macro_cv": (comparison.get(algo) or {}).get("f1_macro_mean")
                    if algo
                    else None,
                    "samples_used": micro.get("samples_used") or local.get("samples_used"),
                    "features": micro.get("features") or local.get("features") or [],
                    "feature_catalog": micro.get("feature_catalog")
                    or local.get("feature_catalog")
                    or [],
                    "selection_reason": micro.get("selection_reason")
                    or local.get("selection_reason"),
                    "ranking": micro.get("ranking") or local.get("ranking") or [],
                    "model_path": micro.get("model_path") or local.get("model_path"),
                }
                active_path.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except Exception as sync_exc:
                results["active_model_sync_error"] = str(sync_exc)
        except Exception as exc:
            results["train_microservice_error"] = str(exc)

    return results
