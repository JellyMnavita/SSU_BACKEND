from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0015_alter_reportaisettings_public_map_retention_days"),
    ]

    operations = [
        migrations.AddField(
            model_name="reportaisettings",
            name="accent_theme",
            field=models.CharField(
                choices=[
                    ("bleu", "Bleu"),
                    ("vert", "Vert"),
                    ("jaune", "Jaune"),
                    ("gris", "Gris"),
                ],
                default="bleu",
                help_text="Thème couleur de la plateforme (boutons, surbrillances, accents).",
                max_length=10,
            ),
        ),
    ]
