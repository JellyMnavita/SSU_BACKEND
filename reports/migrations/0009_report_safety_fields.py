# Generated manually — champs anti-enlèvement + sources mobile

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0008_news_ingest_system_reports"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="report",
            name="valid_source_combination",
        ),
        migrations.AlterField(
            model_name="report",
            name="picture",
            field=models.ImageField(
                blank=True, null=True, upload_to="reports/images/"
            ),
        ),
        migrations.AlterField(
            model_name="report",
            name="source",
            field=models.CharField(
                choices=[
                    ("U", "User"),
                    ("C", "Citizen"),
                    ("S", "System"),
                    ("A", "Admin"),
                    ("O", "SOS"),
                    ("Q", "Quick"),
                    ("W", "Witness"),
                ],
                default="C",
                max_length=1,
            ),
        ),
        migrations.AddField(
            model_name="report",
            name="incident_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("vol", "Vol / cambriolage"),
                    ("kidnapping", "Enlèvement / tentative"),
                    ("agression", "Agression"),
                    ("violence", "Violence armée"),
                    ("vandalisme", "Vandalisme"),
                    ("accident", "Accident"),
                    ("autre", "Autre"),
                ],
                default="autre",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="report",
            name="vehicle_info",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AddField(
            model_name="report",
            name="direction",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AddField(
            model_name="report",
            name="license_plate",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="report",
            name="is_anonymous",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="report",
            name="is_witness",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="report",
            name="mobile_local_id",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="ID SQLite côté app mobile Bokengi (sync).",
                null=True,
            ),
        ),
        migrations.AddConstraint(
            model_name="report",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(source="U", user__isnull=False)
                    | models.Q(source="C", citizen__isnull=False)
                    | models.Q(
                        source__in=["S", "A"],
                        user__isnull=True,
                        citizen__isnull=True,
                    )
                    | models.Q(source__in=["O", "Q", "W"], user__isnull=False)
                ),
                name="valid_source_combination",
            ),
        ),
    ]
