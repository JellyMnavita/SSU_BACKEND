from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from .models import TypeUser
from django.utils import timezone
from rest_framework_simplejwt.exceptions import TokenError
from django.conf import settings
from django.core.mail import send_mail
import secrets
from .models import UserActivityLog
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core import exceptions
from django.template.loader import render_to_string

User = get_user_model()

class UserActivityLogSerializer(serializers.ModelSerializer):
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = UserActivityLog
        fields = [
            'id', 
            'username',
            'action',
            'action_display',
            'ip_address',
            'timestamp',
            'additional_data'
        ]
        read_only_fields = fields
      
        
class LoginSerializer(serializers.Serializer):
    username_or_email = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    def validate(self, data):
        username_or_email = data.get("username_or_email")
        password = data.get("password")

        # Essayer de s'authentifier avec le username d'abord
        user = authenticate(username=username_or_email, password=password)

        # Si l'authentification échoue, essayer avec l'email
        if user is None:
            try:
                user_with_email = User.objects.get(email=username_or_email)
                user = authenticate(
                    username=user_with_email.username, password=password
                )
            except User.DoesNotExist:
                pass

        if user is None:
            raise serializers.ValidationError(
                "Identifiants invalides. Veuillez réessayer."
            )

        if not user.is_verified:
            raise serializers.ValidationError(
                "Votre compte n'est pas encore vérifié. Veuillez vérifier votre email."
            )

        data["user"] = user
        return data


class RefreshTokenSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def validate(self, attrs):
        refresh_token = attrs["refresh"]

        try:
            refresh = RefreshToken(refresh_token)
            data = {"access": str(refresh.access_token)}

            # Rotation des refresh tokens (optionnel mais recommandé)
            if settings.SIMPLE_JWT.get("ROTATE_REFRESH_TOKENS", False):
                refresh.set_jti()
                refresh.set_exp()
                data["refresh"] = str(refresh)

            return data
        except TokenError as e:
            raise serializers.ValidationError({"refresh": str(e)})


class UserSerializer(serializers.ModelSerializer):
    """Sérialiseur pour afficher les infos des utilisateurs"""

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "phone_user",
            "profilePicture_user",
            "is_verified",
        )


class InscriptionSerializer(serializers.ModelSerializer):
    """Sérialiseur pour l'inscription avec validation de mot de passe sécurisé"""

    password = serializers.CharField(
        write_only=True,
        min_length=8,  # Minimum 8 caractères
        style={'input_type': 'password'},  # Pour masquer le mot de passe dans les réponses
        trim_whitespace=False,  # Ne pas supprimer les espaces (pour détection de mots de passe faibles)
    )

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "password",
            "phone_user",
            "profilePicture_user",
            "agreementTermsUse_user",
            "sexe_user",
        )

    def validate_password(self, value):
        """Validation personnalisée pour le mot de passe"""
        try:
            # Utilise les validateurs de mot de passe intégrés de Django
            validate_password(value)
        except exceptions.ValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        
        # Vous pouvez ajouter des validations supplémentaires ici si nécessaire
        if value.lower() == value:
            raise serializers.ValidationError("Le mot de passe doit contenir au moins une majuscule.")
        if value.isalnum():
            raise serializers.ValidationError("Le mot de passe doit contenir au moins un caractère spécial.")
        if self.initial_data.get('username').lower() in value.lower():
            raise serializers.ValidationError("Le mot de passe ne doit pas contenir votre nom d'utilisateur.")
        
        return value

    def create(self, validated_data):
        user_type = TypeUser.objects.get(id=5)
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],  # Django hash automatiquement le mot de passe
            phone_user=validated_data.get("phone_user", ""),
            profilePicture_user=validated_data.get("profilePicture_user", None),
            agreementTermsUse_user=validated_data["agreementTermsUse_user"],
            type_user=user_type,
            sexe_user=validated_data.get("sexe_user", ""),
        )
        user.send_verification_email()  # Envoi du code de validation
        return user


class CreatePriviligeSerializer(serializers.ModelSerializer):
    """Sérialiseur pour la création des comptes gouvernementaux ou d'entreprise"""

    password = serializers.CharField(
        write_only=True,
        min_length=6,
        required=False
    )
    type_user = serializers.PrimaryKeyRelatedField(queryset=TypeUser.objects.all())

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "password",
            "phone_user",
            "profilePicture_user",
            "agreementTermsUse_user",
            "type_user",
            "sexe_user",
        )

    def create(self, validated_data):
        # Si pas de mot de passe fourni → on en génère un
        password = validated_data.pop("password", None)
        if not password:
            alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
            password = ''.join(secrets.choice(alphabet) for _ in range(12))

        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=password,
            phone_user=validated_data.get("phone_user", ""),
            profilePicture_user=validated_data.get("profilePicture_user", None),
            agreementTermsUse_user=validated_data["agreementTermsUse_user"],
            type_user=validated_data["type_user"],
            sexe_user=validated_data.get("sexe_user", ""),
        )

        user.is_verified = True
        user.save()

        self.send_privileged_account_email(user, password)
        return user

    def send_privileged_account_email(self, user, password):
        """Envoi de l'email HTML avec bouton de connexion"""

        subject = "✅ Votre compte privilégié a été créé"

        login_url = "https://ssu-kinshasa.com/login"  

        html_message = render_to_string("emails/privileged_account_email.html", {
            "user": user,
            "password": password,
            "login_url": login_url,
        })

        send_mail(
            subject=subject,
            message="Votre compte a été créé. Veuillez consulter l'e-mail HTML pour les détails.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
            html_message=html_message,
        )

class SuperUserSerializer(serializers.ModelSerializer):
    """Sérialiseur pour créer un superutilisateur via API"""

    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ("username", "email", "password")

    def create(self, validated_data):
        return User.objects.create_superuser(**validated_data)

class VerificationCodeSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=6, required=True)
    email = serializers.EmailField(required=True)

    def validate(self, data):
        email = data.get("email")
        code = data.get("code")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                "Aucun utilisateur avec cet email n'a été trouvé."
            )

        if user.is_verified:
            raise serializers.ValidationError("Ce compte a déjà été vérifié.")

        if user.verification_code != code:
            raise serializers.ValidationError("Code de vérification incorrect.")

        if user.code_expiration and user.code_expiration < timezone.now():
            raise serializers.ValidationError("Le code de vérification a expiré.")

        return data

class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Sérialiseur dédié aux mises à jour
    (exclut les champs sensibles comme le type_user)
    """
    class Meta:
        model = User
        fields = (
            "username", "email", "phone_user",
            "profilePicture_user", "sexe_user"
        )
        extra_kwargs = {
            'email': {'required': False},
            'username': {'required': False}
        }

    def validate_email(self, value):
        """Valide que l'email n'est pas déjà utilisé"""
        if User.objects.filter(email=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("Cet email est déjà utilisé.")
        return value
    
    
class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Aucun utilisateur avec cet email.")
        return value

class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password]
    )
    confirm_password = serializers.CharField(required=True, write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Les mots de passe ne correspondent pas."})
        return data