from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0009_report_safety_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="reportaisettings",
            name="auto_reject_enabled",
            field=models.BooleanField(
                default=True,
                help_text="Autoriser l'IA à rejeter automatiquement les signalements à très faible score.",
            ),
        ),
        migrations.AddField(
            model_name="reportaisettings",
            name="auto_reject_citizen_reports",
            field=models.BooleanField(
                default=False,
                help_text="Inclure les signalements citoyens (C/U/W/Q) dans l'auto-rejet.",
            ),
        ),
        migrations.AddField(
            model_name="reportaisettings",
            name="auto_reject_score_threshold",
            field=models.FloatField(
                default=0.15,
                help_text="Score fusion maximal pour déclencher un rejet automatique (0–1).",
            ),
        ),
    ]
