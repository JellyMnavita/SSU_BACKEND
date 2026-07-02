from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0013_report_notification"),
    ]

    operations = [
        migrations.AddField(
            model_name="reportaisettings",
            name="public_map_retention_days",
            field=models.PositiveIntegerField(
                default=30,
                help_text="Nombre de jours d'affichage des signalements validés sur la carte publique (0 = illimité).",
            ),
        ),
    ]
