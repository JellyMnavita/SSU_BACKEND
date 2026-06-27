from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from .serializers import (
    InscriptionSerializer,
    SuperUserSerializer,
    UserSerializer,
    VerificationCodeSerializer,
    LoginSerializer,
    RefreshTokenSerializer,
    CreatePriviligeSerializer,
    AdminUserUpdateSerializer,
    UserUpdateSerializer,
    PasswordResetSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ChangePasswordSerializer,
    NotificationPreferencesSerializer,
)
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from .permissions import RoleBasedAccess, IsAdminUserType, IsOwnerOrAdmin
from .models import UserActivityLog
from .serializers import UserActivityLogSerializer
from django.http import HttpResponse
import csv
from django.utils import timezone
from datetime import timedelta
import secrets
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import base64
import os
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings


from rest_framework import status
from .session_utils import (
    get_refresh_jti,
    list_active_sessions,
    register_user_session,
    remove_user_session,
    revoke_other_sessions,
    revoke_session,
)
from citizens.services import link_citizen_reports_to_user

User = get_user_model()

class TokenRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")
        if refresh_token is None:
            return Response({"error": "Aucun refresh token fourni."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            old_refresh = RefreshToken(refresh_token)
            access_token = str(old_refresh.access_token)

            response = Response({"access": access_token}, status=status.HTTP_200_OK)

            if settings.SIMPLE_JWT.get("ROTATE_REFRESH_TOKENS", False):
                if settings.SIMPLE_JWT.get("BLACKLIST_AFTER_ROTATION", False):
                    try:
                        old_refresh.blacklist()
                    except AttributeError:
                        return Response({"error": "La blacklist n'est pas bien activée."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                # 👉 Extraire user_id depuis le token
                user_id = old_refresh["user_id"]
                try:
                    user = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    return Response({"error": "Utilisateur non trouvé."}, status=status.HTTP_404_NOT_FOUND)

                # Créer un nouveau refresh token
                new_refresh = RefreshToken.for_user(user)
                remove_user_session(user, str(old_refresh.get("jti")))
                register_user_session(user, str(new_refresh["jti"]), request)
                response.set_cookie(
                    key="refresh_token",
                    value=str(new_refresh),
                    httponly=True,
                    secure=not settings.DEBUG,
                    samesite="Lax",
                    max_age=3 * 24 * 60 * 60,
                )

            return response

        except TokenError:
            return Response({"error": "Refresh token invalide ou expiré."}, status=status.HTTP_401_UNAUTHORIZED)


User = get_user_model()


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            
            user = serializer.validated_data["user"]
            link_citizen_reports_to_user(user)
            # Générer les tokens JWT
            refresh = RefreshToken.for_user(user)
            response = Response({
                "access": str(refresh.access_token),
                "user": UserSerializer(user).data,
            }, status=status.HTTP_200_OK,)

            # Le refresh token dans un cookie sécurisé
            response.set_cookie(
                key="refresh_token",
                value=str(refresh),
                httponly=True,
                secure=not settings.DEBUG,  # cookie local HTTP en DEBUG, HTTPS en production
                samesite="Lax",  # ou "None" si domaine différent
                max_age=3 * 24 * 60 * 60  # 3 jours
            )
            register_user_session(user, str(refresh["jti"]), request)
            return response
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LogoutView(APIView):
    
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.COOKIES.get("refresh_token")
            if refresh_token:
                token = RefreshToken(refresh_token)
                remove_user_session(request.user, str(token.get("jti")))
                token.blacklist()

            response = Response({"message": "Déconnexion réussie"}, status=status.HTTP_200_OK)
            response.delete_cookie("refresh_token")
            return response
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
         
class InscriptionView(generics.CreateAPIView):
    """API pour inscrire un utilisateur normal"""
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = InscriptionSerializer

class CreatePriviligeView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [IsAdminUserType]
    serializer_class = CreatePriviligeSerializer

class CreateSuperUserView(generics.CreateAPIView):
    """API pour créer un superutilisateur"""
    queryset = User.objects.all()
    permission_classes = [IsAdminUser]  # Seuls les admins peuvent créer un superuser
    serializer_class = SuperUserSerializer

class VerifyAccountView(APIView):
    def post(self, request):
        serializer = VerificationCodeSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data["email"]
            user = User.objects.get(email=email)
            user.is_verified = True
            user.save()
            linked = link_citizen_reports_to_user(user)
            return Response(
                {
                    "message": "Compte vérifié avec succès!",
                    "linked_reports": linked,
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ResendVerificationCodeView(APIView):
    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response(
                {"error": "L'email est requis."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"error": "Aucun utilisateur avec cet email n'a été trouvé."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if user.is_verified:
            return Response(
                {"error": "Ce compte a déjà été vérifié."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.send_verification_email()
        return Response(
            {"message": "Un nouveau code de vérification a été envoyé à votre email."},
            status=status.HTTP_200_OK,
        )

class UserListView(generics.ListAPIView):
    """
    API pour lister tous les utilisateurs
    Accessible uniquement aux administrateurs
    """

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminUserType]

class UserRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """
    API pour :
    - Voir son profil (GET)
    - Modifier son profil (PATCH/PUT)
    - Désactiver son compte (DELETE)
    """

    queryset = User.objects.all()

    def get_serializer_class(self):
        if self.request.method == "GET":
            return UserSerializer
        if self.request.method in ["PUT", "PATCH"]:
            if (
                self.request.user.is_authenticated
                and getattr(self.request.user.type_user, "code_typeUser", None) == "ADMIN"
            ):
                return AdminUserUpdateSerializer
            return UserUpdateSerializer
        return UserSerializer

    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        mode = (request.query_params.get("mode") or "").strip().lower()
        if mode == "delete":
            # Suppression "logique" : anonymise les données et désactive le compte
            # (évite de casser des FK vers reports, sessions, etc.).
            user.is_active = False
            user.is_verified = False
            user.email = f"deleted+{user.id}@example.invalid"
            user.username = f"deleted_{user.id}"
            user.phone_user = ""
            user.sexe_user = ""
            user.agreementTermsUse_user = False
            try:
                user.profilePicture_user = None
            except Exception:
                pass
            user.save()
            return Response(
                {"message": "Compte supprimé (anonymisé) avec succès."},
                status=status.HTTP_204_NO_CONTENT,
            )

        user.is_active = False
        user.save()
        return Response(
            {"message": "Compte désactivé avec succès."},
            status=status.HTTP_204_NO_CONTENT,
        )

class AdminUserManagementView(generics.RetrieveUpdateDestroyAPIView):
    """
    API pour les administrateurs :
    - Voir/modifier/supprimer n'importe quel utilisateur
    """

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminUserType]

class PasswordResetView(APIView):
    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)

class UserActivityListView(generics.ListAPIView):
    serializer_class = UserActivityLogSerializer
    permission_classes = [IsAdminUserType]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return UserActivityLog.objects.all()
        return UserActivityLog.objects.filter(user=user)

class ExportUserActivityView(APIView):
    permission_classes = [IsAdminUserType]

    def get(self, request):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="user_activities.csv"'

        writer = csv.writer(response)
        writer.writerow(["Username", "Action", "IP Address", "Timestamp"])

        for log in UserActivityLog.objects.all():
            writer.writerow(
                [
                    log.user.username,
                    log.get_action_display(),
                    log.ip_address,
                    log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                ]
            )

        return response

class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data["email"]
            user = User.objects.get(email=email)

            # Génération d'un token sécurisé
            token = secrets.token_urlsafe(50)
            user.password_reset_token = token
            user.password_reset_token_expiry = timezone.now() + timedelta(hours=1)
            user.save()

            # Construction du lien
            reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"

            # Préparation de l'email HTML
            subject = "Réinitialisation de votre mot de passe"
            def get_logo_base64():
                try:
                    logo_path = os.path.join(settings.BASE_DIR, 'static/images/logo.png')
                    with open(logo_path, 'rb') as f:
                        return base64.b64encode(f.read()).decode('utf-8')
                except:
                    return None  # Fallback si problème
            context = {
                "logo_data": get_logo_base64(),
                "username": user.username,
                "reset_link": reset_link,
                "expiration_hours": 1,
                "support_email": settings.SUPPORT_EMAIL,
                "app_name": settings.APP_NAME,
            }

            # Rendu du template HTML
            html_content = render_to_string("emails/password_reset.html", context)
            text_content = strip_tags(
                html_content
            )  # Version texte pour les clients mail simples

            # Envoi de l'email
            from users.email_utils import send_transactional_email

            send_transactional_email(
                subject="Réinitialisation de votre mot de passe — SSU Bokengi",
                plain_body=(
                    f"Bonjour {user.username},\n\n"
                    f"Pour réinitialiser votre mot de passe, ouvrez ce lien (valide 1 h) :\n"
                    f"{reset_link}\n\n"
                    f"Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.\n"
                ),
                html_body=html_content,
                to=[user.email],
            )

            return Response({"message": "Un email de réinitialisation a été envoyé."})
        return Response(serializer.errors, status=400)

class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        """Vérifie la validité du token (pour le frontend)"""
        token = request.query_params.get('token')
        
        if not token:
            return Response({"error": "Token manquant."}, status=400)
        
        try:
            user = User.objects.get(
                password_reset_token=token,
                password_reset_token_expiry__gt=timezone.now()
            )
            return Response({
                "valid": True,
                "email": user.email,
                "message": "Token valide."
            })
        except User.DoesNotExist:
            return Response({
                "valid": False,
                "error": "Token invalide ou expiré."
            }, status=400)

    def post(self, request):
        """Traite la réinitialisation du mot de passe"""
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
            
        token = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]

        try:
            user = User.objects.get(
                password_reset_token=token,
                password_reset_token_expiry__gt=timezone.now()
            )
        except User.DoesNotExist:
            return Response({"error": "Token invalide ou expiré."}, status=400)

        # Mise à jour du mot de passe
        user.set_password(new_password)
        user.password_reset_token = None
        user.password_reset_token_expiry = None
        user.save()

        # Invalider les tokens JWT existants
        OutstandingToken.objects.filter(user=user).delete()

        return Response({"message": "Mot de passe réinitialisé avec succès."})


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        current_password = serializer.validated_data["current_password"]
        new_password = serializer.validated_data["new_password"]

        if not user.check_password(current_password):
            return Response(
                {"current_password": ["Mot de passe actuel incorrect."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save()

        current_jti = get_refresh_jti(request)
        revoke_other_sessions(user, keep_jti=current_jti)

        return Response({"message": "Mot de passe modifié avec succès."})


class UserNotificationPreferencesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = NotificationPreferencesSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        serializer = NotificationPreferencesSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        prefs = dict(request.user.notification_preferences or {})
        prefs.update(serializer.validated_data)
        request.user.notification_preferences = prefs
        request.user.save(update_fields=["notification_preferences"])

        return Response(NotificationPreferencesSerializer(request.user).data)


class UserSessionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        current_jti = get_refresh_jti(request)
        sessions = list_active_sessions(request.user, current_jti=current_jti)
        return Response({"sessions": sessions, "current_jti": current_jti})


class UserSessionRevokeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, jti: str):
        current_jti = get_refresh_jti(request)
        if not revoke_session(request.user, jti, current_jti=current_jti):
            return Response(
                {"error": "Impossible de révoquer la session courante."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"message": "Session déconnectée."})