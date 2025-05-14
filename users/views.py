
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
    UserUpdateSerializer,
    PasswordResetSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
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

User = get_user_model()


class TokenRefreshView(APIView):
    """
    Rafraîchit le token d'accès à partir du refresh token stocké dans un cookie HttpOnly.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")

        if refresh_token is None:
            return Response({"error": "Aucun refresh token fourni."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            refresh = RefreshToken(refresh_token)
            access_token = str(refresh.access_token)

            response = Response({"access": access_token}, status=status.HTTP_200_OK)

            # Rotation du refresh token (si activée dans SIMPLE_JWT)
            if getattr(settings, "SIMPLE_JWT", {}).get("ROTATE_REFRESH_TOKENS", False):
                new_refresh = str(refresh)
                response.set_cookie(
                    key="refresh_token",
                    value=new_refresh,
                    httponly=True,
                    secure=True,
                    samesite="Lax",  # ou "None" si cross-domain
                    max_age=3 * 24 * 60 * 60,
                )

            return response

        except Exception as e:
            return Response({"error": "Token invalide ou expiré."}, status=status.HTTP_401_UNAUTHORIZED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            
            user = serializer.validated_data["user"]
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
                secure=True,  # si en production avec HTTPS
                samesite="Lax",  # ou "None" si domaine différent
                max_age=3 * 24 * 60 * 60  # 3 jours
            )
            return response
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.COOKIES.get("refresh_token")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()

            response = Response({"message": "Déconnexion réussie"}, status=status.HTTP_205_RESET_CONTENT)
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
            return Response(
                {"message": "Compte vérifié avec succès!"}, status=status.HTTP_200_OK
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
    - Supprimer son compte (DELETE)
    """

    queryset = User.objects.all()

    def get_serializer_class(self):
        if self.request.method == "GET":
            return UserSerializer  # Pour la lecture
        elif self.request.method in ["PUT", "PATCH"]:
            return UserUpdateSerializer  # Pour les modifications
        return UserSerializer  # Fallback

    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]  # Nouvelle permission


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
            email = EmailMultiAlternatives(
                subject,
                text_content,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                reply_to=[settings.SUPPORT_EMAIL],
            )
            email.attach_alternative(html_content, "text/html")
            email.send()

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