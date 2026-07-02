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
            name="PolicePost",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("commune", models.CharField(max_length=100)),
                ("address", models.CharField(blank=True, default="", max_length=255)),
                ("latitude", models.FloatField()),
                ("longitude", models.FloatField()),
                ("patrol_radius_m", models.PositiveIntegerField(default=1500)),
                ("post_type", models.CharField(
                    choices=[
                        ("commissariat", "Commissariat"),
                        ("poste", "Poste de police"),
                        ("patrouille", "Base de patrouille"),
                        ("autre", "Autre"),
                    ],
                    default="commissariat",
                    max_length=20,
                )),
                ("contact_phone", models.CharField(blank=True, default="", max_length=30)),
                ("officers_count", models.PositiveSmallIntegerField(blank=True, default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="police_posts",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "verbose_name": "Poste police",
                "verbose_name_plural": "Postes police",
                "ordering": ["-updated_at"],
            },
        ),
    ]
