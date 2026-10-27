from django.conf import settings
from django.db import models


class PolicePost(models.Model):
    """Poste / commissariat géré par un compte police sur la carte."""

    POST_TYPE_CHOICES = [
        ("commissariat", "Commissariat"),
        ("poste", "Poste de police"),
        ("patrouille", "Base de patrouille"),
        ("autre", "Autre"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="police_posts",
    )
    name = models.CharField(max_length=120)
    commune = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True, default="")
    latitude = models.FloatField()
    longitude = models.FloatField()
    patrol_radius_m = models.PositiveIntegerField(
        default=1500,
        help_text="Rayon de veille opérationnelle autour du poste (mètres).",
    )
    post_type = models.CharField(max_length=20, choices=POST_TYPE_CHOICES, default="commissariat")
    contact_phone = models.CharField(max_length=30, blank=True, default="")
    officers_count = models.PositiveSmallIntegerField(default=0, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Poste police"
        verbose_name_plural = "Postes police"

    def __str__(self):
        return f"{self.name} ({self.commune})"

