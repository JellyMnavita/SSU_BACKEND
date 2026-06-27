from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0011_report_picture_sha256"),
    ]

    operations = [
        migrations.AddField(
            model_name="reportaisettings",
            name="auto_vision_retrain_weekly",
            field=models.BooleanField(
                default=False,
                help_text="Réentraîner le modèle vision chaque semaine (dimanche 3h) si le dataset a changé.",
            ),
        ),
        migrations.AddField(
            model_name="reportaisettings",
            name="vision_retrain_after_exports",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Réentraîner automatiquement après N exports/corrections (0 = désactivé).",
            ),
        ),
    ]
