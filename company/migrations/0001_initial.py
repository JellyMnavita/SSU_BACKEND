from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CompanySite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("commune", models.CharField(max_length=100)),
                ("address", models.CharField(blank=True, default="", max_length=255)),
                ("latitude", models.FloatField()),
                ("longitude", models.FloatField()),
                ("alert_radius_m", models.PositiveIntegerField(default=1000)),
                (
                    "site_type",
                    models.CharField(
                        choices=[
                            ("bureau", "Bureau"),
                            ("entrepot", "Entrepôt"),
                            ("chantier", "Chantier"),
                            ("commerce", "Commerce"),
                            ("autre", "Autre"),
                        ],
                        default="bureau",
                        max_length=20,
                    ),
                ),
                (
                    "is_planned",
                    models.BooleanField(
                        default=False,
                        help_text="Site envisagé (implantation future) plutôt qu'opérationnel.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="company_sites",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Site entreprise",
                "verbose_name_plural": "Sites entreprise",
                "ordering": ["-updated_at"],
            },
        ),
    ]
