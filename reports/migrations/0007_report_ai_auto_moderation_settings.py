from django.db import migrations, models


def create_default_ai_settings(apps, schema_editor):
    ReportAISettings = apps.get_model("reports", "ReportAISettings")
    ReportAISettings.objects.get_or_create(pk=1, defaults={"auto_apply_moderation": False})


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0006_report_ai_async_moderation"),
    ]

    operations = [
        migrations.AddField(
            model_name="report",
            name="ai_moderation_auto_applied",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="ReportAISettings",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "auto_apply_moderation",
                    models.BooleanField(
                        default=False,
                        help_text="Appliquer automatiquement la recommandation IA au statut du signalement.",
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Paramètres IA signalements",
                "verbose_name_plural": "Paramètres IA signalements",
            },
        ),
        migrations.RunPython(create_default_ai_settings, migrations.RunPython.noop),
    ]
