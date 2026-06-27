# Generated manually for safety app

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("reports", "0009_report_safety_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TrustedContact",
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
                ("name", models.CharField(max_length=120)),
                ("phone", models.CharField(max_length=32)),
                ("relationship", models.CharField(blank=True, default="", max_length=80)),
                ("mobile_local_id", models.PositiveIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="trusted_contacts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
        migrations.CreateModel(
            name="TrackingSession",
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
                ("token", models.CharField(max_length=64, unique=True)),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("sos", "SOS"),
                            ("quick", "Signalement rapide"),
                            ("trip", "Trajet"),
                            ("checkin", "Check-in"),
                        ],
                        max_length=16,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Actif"),
                            ("completed", "Terminé"),
                            ("cancelled", "Annulé"),
                        ],
                        default="active",
                        max_length=16,
                    ),
                ),
                ("share_interval_min", models.PositiveSmallIntegerField(default=2)),
                ("last_latitude", models.FloatField(blank=True, null=True)),
                ("last_longitude", models.FloatField(blank=True, null=True)),
                ("last_shared_at", models.DateTimeField(blank=True, null=True)),
                ("mobile_local_id", models.PositiveIntegerField(blank=True, null=True)),
                ("started_at", models.DateTimeField()),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "report",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="tracking_sessions",
                        to="reports.report",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tracking_sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-started_at"],
            },
        ),
        migrations.CreateModel(
            name="Trip",
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
                ("origin_lat", models.FloatField()),
                ("origin_lng", models.FloatField()),
                ("origin_label", models.CharField(blank=True, default="", max_length=200)),
                ("dest_lat", models.FloatField()),
                ("dest_lng", models.FloatField()),
                ("dest_label", models.CharField(blank=True, default="", max_length=200)),
                ("estimated_minutes", models.PositiveIntegerField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Actif"),
                            ("completed", "Terminé"),
                            ("cancelled", "Annulé"),
                            ("alert", "Alerte"),
                        ],
                        default="active",
                        max_length=16,
                    ),
                ),
                ("alert_reason", models.CharField(blank=True, default="", max_length=64)),
                ("mobile_local_id", models.PositiveIntegerField(blank=True, null=True)),
                ("started_at", models.DateTimeField()),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "contact",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="trips",
                        to="safety.trustedcontact",
                    ),
                ),
                (
                    "tracking_session",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="trips",
                        to="safety.trackingsession",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="trips",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-started_at"],
            },
        ),
        migrations.CreateModel(
            name="TrackingPoint",
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
                ("latitude", models.FloatField()),
                ("longitude", models.FloatField()),
                ("recorded_at", models.DateTimeField()),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="points",
                        to="safety.trackingsession",
                    ),
                ),
            ],
            options={
                "ordering": ["recorded_at"],
            },
        ),
        migrations.CreateModel(
            name="CheckIn",
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
                ("duration_minutes", models.PositiveIntegerField()),
                ("due_at", models.DateTimeField()),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "En attente"),
                            ("confirmed", "Confirmé"),
                            ("missed", "Manqué"),
                            ("cancelled", "Annulé"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("auto_sos", models.BooleanField(default=True)),
                ("contact_ids", models.JSONField(blank=True, default=list)),
                ("mobile_local_id", models.PositiveIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tracking_session",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="check_ins",
                        to="safety.trackingsession",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="check_ins",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-due_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="trustedcontact",
            constraint=models.UniqueConstraint(
                fields=("user", "phone"),
                name="unique_trusted_contact_phone_per_user",
            ),
        ),
    ]
