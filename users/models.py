from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.mail import send_mail
from django.db import models
from django.utils import timezone
from django.conf import settings
import secrets
from django.contrib.auth import get_user_model

class TypeUser(models.Model):
    CODE_CHOICES = [
        ('GOV', 'Service gouvernemental'),
        ('COMPANY', 'Entreprise étrangère'),
        ('ADMIN', 'Administrateur principal'),
        ('USER', 'Utilisateur simple'),
    ]
    code_typeUser = models.CharField(max_length=10, choices=CODE_CHOICES, unique=True)
    description_typeUser = models.CharField(max_length=250)

    def __str__(self):
        return self.get_code_typeUser_display()
    
class UserManager(BaseUserManager):
    """Manager personnalisé pour le modèle User avec username comme identifiant principal"""
    
    def create_user(self, username, email, password=None, **extra_fields):
        if not email:
            raise ValueError("L'email est obligatoire")
        if not username:
            raise ValueError("Le nom d'utilisateur est obligatoire")
        
        email = self.normalize_email(email)
        type_user_value = extra_fields.get("type_user")
        if type_user_value is not None and not isinstance(type_user_value, TypeUser):
            extra_fields["type_user"] = TypeUser.objects.get(pk=type_user_value)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(username, email, password, **extra_fields)

class User(AbstractUser):
    """Modèle utilisateur personnalisé"""
    
    SEX_CHOICES = [
        ('M', 'Masculin'),
        ('F', 'Féminin')
    ]
    
    email = models.EmailField(unique=True)
    is_verified = models.BooleanField(default=False)
    verification_code = models.CharField(max_length=6, blank=True)
    code_expiration = models.DateTimeField(null=True, blank=True)
    
    type_user = models.ForeignKey(TypeUser, on_delete=models.PROTECT, null=True) 
    phone_user = models.CharField(max_length=20, blank=True)
    profilePicture_user = models.ImageField(upload_to='profiles/', null=True, blank=True)
    agreementTermsUse_user = models.BooleanField(default=False)
    sexe_user = models.CharField(max_length=10, choices=SEX_CHOICES, blank=True)
    
    password_reset_token = models.CharField(max_length=100, blank=True, null=True)
    password_reset_token_expiry = models.DateTimeField(blank=True, null=True)
    
    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ['email', 'type_user'] # On garde l'email obligatoire pour éviter les problèmes

    def generate_verification_code(self):
        """Génère un code de validation à 6 chiffres et met à jour la date d'expiration."""
        code = secrets.randbelow(1_000_000)
        self.verification_code = f"{code:06d}"
        self.code_expiration = timezone.now() + timezone.timedelta(hours=30)
        self.save()
        return self.verification_code

    def send_verification_email(self):
        """Envoie le code de validation par email."""
        code = self.generate_verification_code()
        subject = "Votre code de vérification"
        message = f"""
        Bonjour {self.username},
        
        Voici votre code de vérification : {code}
        Ce code expirera dans 24 heures.
        
        L'équipe SSU
        """
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,  # Assure-toi que ce paramètre est défini dans settings.py
            [self.email],
            fail_silently=False,
        )

    def __str__(self):
        return self.username

User = get_user_model()

class UserActivityLog(models.Model):
    ACTION_CHOICES = [
        ('LOGIN', 'Connexion'),
        ('LOGOUT', 'Déconnexion'),
        ('PROFILE_UPDATE', 'Mise à jour du profil'),
        ('PASSWORD_CHANGE', 'Changement de mot de passe'),
        ('ACCOUNT_DELETE', 'Suppression de compte'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=255, blank=True)
    additional_data = models.JSONField(default=dict, blank=True)  # Pour stocker des infos supplémentaires
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Journal d'activité"
        verbose_name_plural = "Journaux d'activité"
        
    @classmethod
    def purge_old_records(cls, days=90):
        cutoff_date = timezone.now() - timedelta(days=days)
        cls.objects.filter(timestamp__lt=cutoff_date).delete()
        
    def __str__(self):
        return f"{self.user.username} - {self.get_action_display()} - {self.timestamp}"