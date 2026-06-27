from django.db import models


class TrustedContact(models.Model):
    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="trusted_contacts",
    )
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=32)
    email = models.EmailField(blank=True, default="")
    relationship = models.CharField(max_length=80, blank=True, default="")
    mobile_local_id = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "phone"],
                name="unique_trusted_contact_phone_per_user",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.phone})"


class SafetyAlert(models.Model):
    """Alerte reçue par un contact de confiance (compte Bokengi)."""

    KIND_CHOICES = [
        ("sos", "SOS"),
        ("trip", "Trajet"),
        ("checkin", "Check-in"),
    ]

    recipient = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="safety_alerts_received",
    )
    initiator = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="safety_alerts_sent",
    )
    trusted_contact = models.ForeignKey(
        TrustedContact,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="alerts",
    )
    tracking_session = models.ForeignKey(
        "TrackingSession",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="alerts",
    )
    kind = models.CharField(max_length=16, choices=KIND_CHOICES, default="sos")
    message = models.CharField(max_length=500, blank=True, default="")
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.kind} → {self.recipient_id}"


class TrackingSession(models.Model):
    KIND_CHOICES = [
        ("sos", "SOS"),
        ("quick", "Signalement rapide"),
        ("trip", "Trajet"),
        ("checkin", "Check-in"),
    ]
    STATUS_CHOICES = [
        ("active", "Actif"),
        ("completed", "Terminé"),
        ("cancelled", "Annulé"),
    ]

    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="tracking_sessions",
    )
    token = models.CharField(max_length=64, unique=True)
    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default="active"
    )
    share_interval_min = models.PositiveSmallIntegerField(default=2)
    last_latitude = models.FloatField(null=True, blank=True)
    last_longitude = models.FloatField(null=True, blank=True)
    last_shared_at = models.DateTimeField(null=True, blank=True)
    report = models.ForeignKey(
        "reports.Report",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tracking_sessions",
    )
    mobile_local_id = models.PositiveIntegerField(null=True, blank=True)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.kind} — {self.token}"


class TrackingPoint(models.Model):
    session = models.ForeignKey(
        TrackingSession,
        on_delete=models.CASCADE,
        related_name="points",
    )
    latitude = models.FloatField()
    longitude = models.FloatField()
    recorded_at = models.DateTimeField()

    class Meta:
        ordering = ["recorded_at"]

    def __str__(self):
        return f"Point {self.session.token} @ {self.recorded_at}"


class Trip(models.Model):
    STATUS_CHOICES = [
        ("active", "Actif"),
        ("completed", "Terminé"),
        ("cancelled", "Annulé"),
        ("alert", "Alerte"),
    ]

    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="trips",
    )
    tracking_session = models.ForeignKey(
        TrackingSession,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="trips",
    )
    contact = models.ForeignKey(
        TrustedContact,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="trips",
    )
    origin_lat = models.FloatField()
    origin_lng = models.FloatField()
    origin_label = models.CharField(max_length=200, blank=True, default="")
    dest_lat = models.FloatField()
    dest_lng = models.FloatField()
    dest_label = models.CharField(max_length=200, blank=True, default="")
    estimated_minutes = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="active")
    alert_reason = models.CharField(max_length=64, blank=True, default="")
    mobile_local_id = models.PositiveIntegerField(null=True, blank=True)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"Trajet {self.user_id} → {self.dest_label or self.dest_lat}"


class CheckIn(models.Model):
    STATUS_CHOICES = [
        ("pending", "En attente"),
        ("confirmed", "Confirmé"),
        ("missed", "Manqué"),
        ("cancelled", "Annulé"),
    ]

    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="check_ins",
    )
    duration_minutes = models.PositiveIntegerField()
    due_at = models.DateTimeField()
    confirmed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending")
    auto_sos = models.BooleanField(default=True)
    contact_ids = models.JSONField(default=list, blank=True)
    tracking_session = models.ForeignKey(
        TrackingSession,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="check_ins",
    )
    mobile_local_id = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-due_at"]

    def __str__(self):
        return f"Check-in {self.user_id} — {self.status}"
