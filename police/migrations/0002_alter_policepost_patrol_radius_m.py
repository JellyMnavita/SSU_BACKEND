from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("police", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="policepost",
            name="patrol_radius_m",
            field=models.PositiveIntegerField(
                default=1500,
                help_text="Rayon de veille opérationnelle autour du poste (mètres).",
            ),
        ),
    ]
