from django.db import models


class Report(models.Model):
    DEGREE_CHOICES = [("F", "Faible"), ("M", "Moyen"), ("E", "Elevé")]
    STATUS_CHOICES = [("P", "Pending"), ("V", "Validated"), ("R", "Rejected")]
    SOURCE_CHOICES = [
        ("U", "User"),
        ("C", "Citizen"),
        ("S", "System"),
        ("A", "Admin"),
        ("O", "SOS"),
        ("Q", "Quick"),
        ("W", "Witness"),
    ]
    INCIDENT_TYPE_CHOICES = [
        ("vol", "Vol / cambriolage"),
        ("kidnapping", "Enlèvement / tentative"),
        ("agression", "Agression"),
        ("violence", "Violence armée"),
        ("vandalisme", "Vandalisme"),
        ("accident", "Accident"),
        ("autre", "Autre"),
    ]
    description = models.TextField()
    location = models.CharField(max_length=200)  # Adresse lisible
    longitude = models.FloatField()
    latitude = models.FloatField()
    degree = models.CharField(max_length=1, choices=DEGREE_CHOICES)
    picture = models.ImageField(upload_to="reports/images/", blank=True, null=True)
    picture_sha256 = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text="Empreinte SHA-256 de la photo (anti-doublon signalements).",
    )
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default="P")
    source = models.CharField(max_length=1, choices=SOURCE_CHOICES, default="C")
    incident_type = models.CharField(
        max_length=32,
        choices=INCIDENT_TYPE_CHOICES,
        default="autre",
        blank=True,
    )
    vehicle_info = models.CharField(max_length=200, blank=True, default="")
    direction = models.CharField(max_length=200, blank=True, default="")
    license_plate = models.CharField(max_length=32, blank=True, default="")
    is_anonymous = models.BooleanField(default=False)
    is_witness = models.BooleanField(default=False)
    mobile_local_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="ID SQLite côté app mobile Bokengi (sync).",
    )
    quartier = models.ForeignKey(
        "locations.Quartier", null=True, blank=True, on_delete=models.SET_NULL
    )
    user = models.ForeignKey(
        "users.User", null=True, blank=True, on_delete=models.SET_NULL
    )
    citizen = models.ForeignKey(
        "citizens.Citizen", null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Enrichissement IA (microservices nlp / vision)
    ai_incident_type = models.CharField(max_length=32, blank=True, default="")
    ai_nlp_confidence = models.FloatField(null=True, blank=True)
    ai_vision_results = models.JSONField(null=True, blank=True)
    user_degree_before_ai = models.CharField(
        max_length=1, choices=DEGREE_CHOICES, blank=True, default=""
    )
    ai_recommended_degree = models.CharField(
        max_length=1, choices=DEGREE_CHOICES, blank=True, default=""
    )
    degree_adjusted_by_ai = models.BooleanField(default=False)

    # Traitement IA asynchrone (Celery)
    AI_PROCESSING_STATUS_CHOICES = [
        ("pending", "En file"),
        ("processing", "En cours"),
        ("completed", "Terminé"),
        ("failed", "Échec"),
        ("skipped", "Ignoré"),
    ]
    ai_processing_status = models.CharField(
        max_length=16,
        choices=AI_PROCESSING_STATUS_CHOICES,
        default="pending",
    )
    ai_processing_errors = models.JSONField(null=True, blank=True)
    ai_processed_at = models.DateTimeField(null=True, blank=True)

    # Recommandation de modération IA (V/R/P) — distincte du statut admin
    ai_moderation_recommendation = models.CharField(
        max_length=1, choices=STATUS_CHOICES, blank=True, default=""
    )
    ai_moderation_confidence = models.FloatField(null=True, blank=True)
    ai_moderation_reasons = models.JSONField(null=True, blank=True)
    ai_enrichment_summary = models.JSONField(null=True, blank=True)
    ai_moderation_auto_applied = models.BooleanField(default=False)

    # Signalements créés automatiquement (scraping actualités)
    external_source_url = models.URLField(
        max_length=500,
        blank=True,
        default="",
        help_text="URL de l'article source (signalements système).",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(source="U", user__isnull=False)
                    | models.Q(source="C", citizen__isnull=False)
                    | models.Q(
                        source__in=["S", "A"],
                        user__isnull=True,
                        citizen__isnull=True,
                    )
                    | models.Q(
                        source__in=["O", "Q", "W"],
                        user__isnull=False,
                    )
                ),
                name="valid_source_combination",
            ),
            models.UniqueConstraint(
                fields=["picture_sha256"],
                condition=models.Q(picture_sha256__gt=""),
                name="unique_report_picture_sha256",
            ),
        ]


class ReportNotification(models.Model):
    """Notification in-app pour l'auteur d'un signalement (traitement V/R)."""

    recipient = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="report_notifications",
    )
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    status = models.CharField(max_length=1, choices=Report.STATUS_CHOICES)
    message = models.CharField(max_length=500)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["recipient", "report", "status"],
                name="unique_report_notification_per_status",
            ),
        ]

    def __str__(self):
        return f"RPT-{self.report_id} → {self.recipient_id} ({self.status})"


class ReportAISettings(models.Model):
    """Paramètres globaux IA signalements (singleton pk=1)."""

    auto_apply_moderation = models.BooleanField(
        default=False,
        help_text="Appliquer automatiquement la recommandation IA au statut du signalement.",
    )
    auto_reject_enabled = models.BooleanField(
        default=True,
        help_text="Autoriser l'IA à rejeter automatiquement les signalements à très faible score.",
    )
    auto_reject_citizen_reports = models.BooleanField(
        default=False,
        help_text="Inclure les signalements citoyens (C/U/W/Q) dans l'auto-rejet.",
    )
    auto_reject_score_threshold = models.FloatField(
        default=0.15,
        help_text="Score fusion maximal pour déclencher un rejet automatique (0–1).",
    )
    auto_ingest_news = models.BooleanField(
        default=False,
        help_text="Ingérer automatiquement les actualités sécurité (scraping → signalements source=S).",
    )
    auto_vision_retrain_weekly = models.BooleanField(
        default=False,
        help_text="Réentraîner le modèle vision chaque semaine (dimanche 3h) si le dataset a changé.",
    )
    vision_retrain_after_exports = models.PositiveIntegerField(
        default=0,
        help_text="Réentraîner automatiquement après N exports/corrections (0 = désactivé).",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Paramètres IA signalements"
        verbose_name_plural = "Paramètres IA signalements"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"IA auto-modération: {'ON' if self.auto_apply_moderation else 'OFF'}"


class ScrapedReport(models.Model):
    STATUS_CHOICES = [
        ("P", "Pending"),
        ("T", "Processed"),
        ("R", "Rejected"),
    ]

    url_source = models.URLField(max_length=500, unique=True)
    title = models.CharField(max_length=300)
    content = models.TextField(blank=True, default="")
    image_url = models.URLField(max_length=500, blank=True, default="")
    source_site = models.CharField(max_length=120, blank=True, default="")
    published_label = models.CharField(max_length=120, blank=True, default="")
    date_scraped = models.DateTimeField(auto_now_add=True)
    longitude = models.FloatField(null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    location_label = models.CharField(max_length=200, blank=True, default="")
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default="P")
    reject_reason = models.TextField(blank=True, default="")
    report = models.OneToOneField(
        "Report",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="scraped_article",
    )

    class Meta:
        ordering = ["-date_scraped"]

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"
