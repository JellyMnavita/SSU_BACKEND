from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from .models import TypeUser
from django.utils import timezone
from rest_framework_simplejwt.exceptions import TokenError
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
import secrets
from .models import UserActivityLog
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core import exceptions
from django.template.loader import render_to_string
from common.i18n import validation_error

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
            raise validation_error("ERR_INVALID_CREDENTIALS", self.context)

        if not user.is_verified:
            raise validation_error("ERR_ACCOUNT_NOT_VERIFIED", self.context)

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
    type_user = serializers.CharField(source="type_user.code_typeUser", read_only=True)
    account_tier_display = serializers.CharField(
        source="get_account_tier_display", read_only=True
    )

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "phone_user",
            "profilePicture_user",
            "is_verified",
            "sexe_user",
            "type_user",
            "account_tier",
            "account_tier_display",
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
            raise validation_error("ERR_PASSWORD_UPPERCASE", self.context)
        if value.isalnum():
            raise validation_error("ERR_PASSWORD_SPECIAL", self.context)
        if self.initial_data.get('username').lower() in value.lower():
            raise validation_error("ERR_PASSWORD_CONTAINS_USERNAME", self.context)
        
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
        """Envoi de l'e-mail HTML de bienvenue (style Hostinger)."""
        from django.conf import settings

        app_name = getattr(settings, "APP_NAME", "SSU Bokengi")
        frontend_url = (getattr(settings, "FRONTEND_URL", None) or "http://localhost").rstrip("/")
        login_url = f"{frontend_url}/login"
        account_type = user.type_user.get_code_typeUser_display() if user.type_user else "Compte"

        context = {
            "user": user,
            "password": password,
            "login_url": login_url,
            "app_name": app_name,
            "account_type": account_type,
            "support_email": getattr(settings, "SUPPORT_EMAIL", None),
        }

        html_message = render_to_string("emails/privileged_account_email.html", context)
        plain_message = (
            f"Bonjour {user.username},\n\n"
            f"Votre compte {account_type} sur {app_name} a été créé.\n"
            f"Identifiant : {user.username}\n"
            f"E-mail : {user.email}\n"
            f"Mot de passe temporaire : {password}\n\n"
            f"Connexion : {login_url}\n\n"
            f"Changez votre mot de passe après la première connexion.\n"
            f"L'équipe {app_name}"
        )

        from users.email_utils import send_transactional_email

        send_transactional_email(
            subject=f"Votre compte {app_name} a été créé",
            plain_body=plain_message,
            html_body=html_message,
            to=[user.email],
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
            raise validation_error("ERR_USER_NOT_FOUND_EMAIL", self.context)

        if user.is_verified:
            raise validation_error("ERR_ALREADY_VERIFIED", self.context)

        if user.verification_code != code:
            raise validation_error("ERR_INVALID_VERIFICATION_CODE", self.context)

        if user.code_expiration and user.code_expiration < timezone.now():
            raise validation_error("ERR_VERIFICATION_CODE_EXPIRED", self.context)

        return data

class AdminUserUpdateSerializer(serializers.ModelSerializer):
    """Mise à jour complète par un administrateur (inclut le type)."""

    type_user = serializers.SlugRelatedField(
        slug_field="code_typeUser",
        queryset=TypeUser.objects.all(),
        required=False,
    )
    account_tier = serializers.ChoiceField(
        choices=["NORMAL", "PRO", "PREMIUM"],
        required=False,
    )
    new_password = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
        min_length=8,
    )
    confirm_new_password = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
    )
    admin_password = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
    )

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "phone_user",
            "profilePicture_user",
            "is_verified",
            "sexe_user",
            "type_user",
            "account_tier",
            "new_password",
            "confirm_new_password",
            "admin_password",
        )
        extra_kwargs = {
            "email": {"required": False},
            "username": {"required": False},
        }

    def validate(self, attrs):
        instance = self.instance
        type_user = attrs.get("type_user", getattr(instance, "type_user", None))
        tier = attrs.get("account_tier", getattr(instance, "account_tier", "NORMAL"))
        role_code = getattr(type_user, "code_typeUser", None)
        if tier != "NORMAL" and role_code and role_code != "USER":
            raise validation_error("ERR_TIER_CITIZEN_ONLY", self.context, field="account_tier")

        new_password = (attrs.get("new_password") or "").strip()
        if new_password:
            confirm_new_password = (attrs.get("confirm_new_password") or "").strip()
            admin_password = (attrs.get("admin_password") or "").strip()
            if new_password != confirm_new_password:
                raise validation_error(
                    "ERR_PASSWORDS_MISMATCH",
                    self.context,
                    field="confirm_new_password",
                )
            if not admin_password:
                raise validation_error(
                    "ERR_ADMIN_PASSWORD_REQUIRED",
                    self.context,
                    field="admin_password",
                )
            request = self.context.get("request")
            admin_user = getattr(request, "user", None)
            if not admin_user or not admin_user.is_authenticated:
                raise validation_error("ERR_ADMIN_PASSWORD_INVALID", self.context, field="admin_password")
            if not admin_user.check_password(admin_password):
                raise validation_error("ERR_ADMIN_PASSWORD_INVALID", self.context, field="admin_password")
            try:
                validate_password(new_password, user=instance)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"new_password": list(exc.messages)}) from exc
            attrs["new_password"] = new_password
        else:
            attrs.pop("new_password", None)
            attrs.pop("confirm_new_password", None)
            attrs.pop("admin_password", None)

        return attrs

    def update(self, instance, validated_data):
        new_password = validated_data.pop("new_password", None)
        validated_data.pop("confirm_new_password", None)
        validated_data.pop("admin_password", None)

        type_user = validated_data.get("type_user", instance.type_user)
        role_code = getattr(type_user, "code_typeUser", None)
        if role_code and role_code != "USER":
            validated_data["account_tier"] = "NORMAL"
        instance = super().update(instance, validated_data)
        if new_password:
            instance.set_password(new_password)
            instance.save(update_fields=["password"])
        return instance

    def validate_email(self, value):
        if User.objects.filter(email=value).exclude(pk=self.instance.pk).exists():
            raise validation_error("ERR_EMAIL_ALREADY_USED", self.context)
        return value


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Sérialiseur dédié aux mises à jour
    (exclut les champs sensibles comme le type_user)
    """
    type_user = serializers.CharField(source="type_user.code_typeUser", read_only=True)
    account_tier = serializers.CharField(read_only=True)
    account_tier_display = serializers.CharField(
        source="get_account_tier_display", read_only=True
    )

    class Meta:
        model = User
        fields = (
             "id",
            "username",
            "email",
            "phone_user",
            "profilePicture_user",
            "is_verified",
            "sexe_user",
            "type_user",
            "account_tier",
            "account_tier_display",
        )
        extra_kwargs = {
            'email': {'required': False},
            'username': {'required': False}
        }

    def validate_email(self, value):
        """Valide que l'email n'est pas déjà utilisé"""
        if User.objects.filter(email=value).exclude(pk=self.instance.pk).exists():
            raise validation_error("ERR_EMAIL_ALREADY_USED", self.context)
        return value
    
    
class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise validation_error("ERR_USER_NOT_FOUND", self.context)
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
            raise validation_error("ERR_PASSWORDS_MISMATCH", self.context, field="confirm_password")
        return data


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, min_length=8)
    confirm_password = serializers.CharField(required=True, write_only=True)

    def validate(self, data):
        if data["new_password"] != data["confirm_password"]:
            raise validation_error("ERR_PASSWORDS_MISMATCH", self.context, field="confirm_password")
        validate_password(data["new_password"])
        return data


class NotificationPreferencesSerializer(serializers.Serializer):
    email_alerts = serializers.BooleanField(required=False)
    push_notifications = serializers.BooleanField(required=False)
    sms_alerts = serializers.BooleanField(required=False)
    weekly_report = serializers.BooleanField(required=False)
    nearby_incidents = serializers.BooleanField(required=False)

    def validate(self, attrs):
        from .constants import NOTIFICATION_PREFERENCE_KEYS

        unknown = set(attrs.keys()) - NOTIFICATION_PREFERENCE_KEYS
        if unknown:
            raise validation_error(
                "ERR_UNKNOWN_NOTIFICATION_KEYS",
                self.context,
                keys=", ".join(sorted(unknown)),
            )
        return attrs

    def to_representation(self, instance):
        if hasattr(instance, "merged_notification_preferences"):
            return instance.merged_notification_preferences()
        return instance