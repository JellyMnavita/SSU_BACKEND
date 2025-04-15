from django.db import models

SEX_CHOICES = [('M', 'Male'), ('F', 'Female')]
CIVIL_CHOICES = [('S', 'Single'), ('M', 'Married'), ('D', 'Divorced'), ('W', 'Widowed')]

class Citizen(models.Model):
    email = models.EmailField(unique=True)  # Clé de regroupement
    name = models.CharField(max_length=100)
    lastname = models.CharField(max_length=100)
    sexe = models.CharField(max_length=1, choices=SEX_CHOICES)
    birth_date = models.DateField()
    nationality = models.CharField(max_length=50)
    profession = models.CharField(max_length=100, blank=True)
    civil_status = models.CharField(max_length=1, choices=CIVIL_CHOICES)
    quartier = models.ForeignKey('locations.Quartier', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} {self.lastname}"

class CitizenAlternateData(models.Model):
    """Stocke les variations des données pour un même email"""
    citizen = models.ForeignKey(Citizen, on_delete=models.CASCADE, related_name='alternate_data')
    name = models.CharField(max_length=100)
    lastname = models.CharField(max_length=100)
    sexe = models.CharField(max_length=1, choices=SEX_CHOICES)
    nationality = models.CharField(max_length=50)
    profession = models.CharField(max_length=100, blank=True)
    civil_status = models.CharField(max_length=1, choices=CIVIL_CHOICES)
    quartier = models.ForeignKey('locations.Quartier', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)