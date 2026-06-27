from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0005_report_degree_ai_adjustment"),
    ]

    operations = [
        migrations.AddField(
            model_name="report",
            name="ai_processing_status",
            field=models.CharField(
                choices=[
                    ("pending", "En file"),
                    ("processing", "En cours"),
                    ("completed", "Terminé"),
                    ("failed", "Échec"),
                    ("skipped", "Ignoré"),
                ],
                default="pending",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="report",
            name="ai_processing_errors",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="report",
            name="ai_processed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="report",
            name="ai_moderation_recommendation",
            field=models.CharField(
                blank=True,
                choices=[("P", "Pending"), ("V", "Validated"), ("R", "Rejected")],
                default="",
                max_length=1,
            ),
        ),
        migrations.AddField(
            model_name="report",
            name="ai_moderation_confidence",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="report",
            name="ai_moderation_reasons",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="report",
            name="ai_enrichment_summary",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.RunPython(
            code=lambda apps, schema_editor: _backfill_ai_status(apps),
            reverse_code=migrations.RunPython.noop,
        ),
    ]


def _backfill_ai_status(apps):
    Report = apps.get_model("reports", "Report")
    for report in Report.objects.iterator():
        if report.ai_incident_type or report.ai_vision_results:
            report.ai_processing_status = "completed"
        else:
            report.ai_processing_status = "skipped"
        report.save(update_fields=["ai_processing_status"])
