from django.conf import settings
from django.db import models


class CompanySite(models.Model):
    SITE_TYPE_CHOICES = [
        ("bureau", "Bureau"),
        ("entrepot", "Entrepôt"),
        ("chantier", "Chantier"),
        ("commerce", "Commerce"),
        ("autre", "Autre"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="company_sites",
    )
    name = models.CharField(max_length=120)
    commune = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True, default="")
    latitude = models.FloatField()
    longitude = models.FloatField()
    alert_radius_m = models.PositiveIntegerField(default=1000)
    site_type = models.CharField(max_length=20, choices=SITE_TYPE_CHOICES, default="bureau")
    is_planned = models.BooleanField(
        default=False,
        help_text="Site envisagé (implantation future) plutôt qu'opérationnel.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Site entreprise"
        verbose_name_plural = "Sites entreprise"

    def __str__(self):
        return f"{self.name} ({self.commune})"
