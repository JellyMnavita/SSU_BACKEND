from django.db import models


class Report(models.Model):
    DEGREE_CHOICES = [("F", "Faible"), ("M", "Moyen"), ("E", "Elevé")]
    STATUS_CHOICES = [("P", "Pending"), ("V", "Validated"), ("R", "Rejected")]
    SOURCE_CHOICES = [
        ("U", "User"),
        ("C", "Citizen"),
        ("S", "System"),
        ("A", "Admin"),
    ]
    description = models.TextField()
    location = models.CharField(max_length=200)  # Adresse lisible
    longitude = models.FloatField()
    latitude = models.FloatField()
    degree = models.CharField(max_length=1, choices=DEGREE_CHOICES)
    picture = models.ImageField(upload_to="reports/images/")
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default="P")
    source = models.CharField(max_length=1, choices=SOURCE_CHOICES, default="C")
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

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(source='U', user__isnull=False) |
                    models.Q(source='C', citizen__isnull=False) |
                    models.Q(source__in=['S', 'A'], user__isnull=True, citizen__isnull=True)
                ),
                name='valid_source_combination'
            )
        ]

class ScrapedReport(models.Model):
    STATUS_CHOICES = [
        ('P', 'Pending'),
        ('T', 'Processed'),
        ('R', 'Rejected')
    ]
    
    url_source = models.URLField(max_length=500)
    title = models.CharField(max_length=200)
    content = models.TextField()
    date_scraped = models.DateTimeField(auto_now_add=True)
    longitude = models.FloatField(null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default='P')

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"
