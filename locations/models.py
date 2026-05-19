from django.db import models


class Commune(models.Model):
    """Division administrative de Kinshasa"""
    nom = models.CharField(max_length=100, unique=True)
    superficie = models.FloatField(help_text="En km²") 
    population = models.PositiveIntegerField()
    maire = models.CharField(max_length=100)
    contact_urgence = models.CharField(max_length=20)
    date_creation = models.DateField()

    class Meta:
        verbose_name = "Commune"
        verbose_name_plural = "Communes"
        ordering = ['nom']

    def __str__(self):
        return self.nom

class Quartier(models.Model):
    """Sous-division des communes"""
    commune = models.ForeignKey(Commune, on_delete=models.PROTECT, related_name='quartiers')
    nom = models.CharField(max_length=100)
    #code_postal = models.CharField(max_length=10, blank=True)
    limites_gps = models.TextField(help_text="Coordonnées JSON des limites du quartier")
    points_interet = models.JSONField(default=list, help_text="Hôpitaux, commissariats, etc.")
    taux_criminalite = models.FloatField(default=0.0)

    class Meta:
        unique_together = ('commune', 'nom')
        verbose_name = "Quartier"
        ordering = ['commune__nom', 'nom']

    def __str__(self):
        return f"{self.nom}, {self.commune.nom}"

class LieuStrategique(models.Model):
    """Points importants pour la sécurité"""
    TYPE_CHOICES = [
        ('POLICE', 'Commissariat'),
        ('HOPITAL', 'Hôpital'),
        ('CASERNE', 'Caserne militaire'),
        ('MARCHE', 'Marché'),
    ]
    
    quartier = models.ForeignKey(Quartier, on_delete=models.CASCADE)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    nom = models.CharField(max_length=200)
    adresse = models.TextField()
    longitude = models.FloatField()
    latitude = models.FloatField()
    contact = models.CharField(max_length=20)
    responsable = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Lieu stratégique"
        ordering = ['quartier', 'type']

    def __str__(self):
        return f"{self.get_type_display()} - {self.nom}"