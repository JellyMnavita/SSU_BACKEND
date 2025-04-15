from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .models import TypeUser

@receiver(post_migrate)
def create_default_type_users(sender, **kwargs):
    if sender.name == "users":  # Vérifie que la migration concerne l’app users
        types = [
            ('CITIZEN', 'Citoyen inscrit'),
            ('GOV', 'Service gouvernemental'),
            ('COMPANY', 'Entreprise étrangère'),
            ('ADMIN', 'Administrateur principal'),
            ('USER', 'Utilisateur simple'),
        ]
        for code, description in types:
            TypeUser.objects.get_or_create(code_typeUser=code, description_typeUser=description)
