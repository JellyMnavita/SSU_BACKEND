from django.utils import timezone
from .models import UserActivityLog
import json
from urllib.parse import urlparse

class UserActivityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Détection des actions avant traitement
        is_login = (request.path == '/api/user/login/' and request.method == 'POST')
        is_register = (request.path == '/api/user/register/' and request.method == 'POST')
        is_password_change = (request.path == '/api/user/password/change/' and request.method == 'POST')
        
        response = self.get_response(request)
        
        # Traitement après réponse
        try:
            if is_login and response.status_code == 200:
                self._handle_login_success(request, response)
            elif is_register and response.status_code == 201:
                self._handle_registration(request, response)
            elif is_password_change and response.status_code == 200:
                self._handle_password_change(request)
            elif request.user.is_authenticated:
                self._handle_common_actions(request)
        except Exception as e:
            # Log l'erreur sans interrompre le flux
            print(f"Error logging activity: {str(e)}")
        
        return response

    def _handle_login_success(self, request, response):
        """Gère le log des connexions réussies"""
        try:
            user_data = json.loads(response.content)
            user_id = user_data.get('user', {}).get('id')
            if user_id:
                UserActivityLog.objects.create(
                    user_id=user_id,
                    action='LOGIN_SUCCESS',
                    ip_address=self._get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    additional_data={
                        'path': request.path,
                        'method': request.method,
                    }
                )
        except json.JSONDecodeError:
            pass

    def _handle_registration(self, request, response):
        """Gère le log des nouvelles inscriptions"""
        try:
            user_data = json.loads(response.content)
            user_id = user_data.get('id')
            if user_id:
                UserActivityLog.objects.create(
                    user_id=user_id,
                    action='ACCOUNT_CREATION',
                    ip_address=self._get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    additional_data={
                        'path': request.path,
                        'method': request.method,
                    }
                )
        except json.JSONDecodeError:
            pass

    def _handle_password_change(self, request):
        """Gère le log des changements de mot de passe"""
        UserActivityLog.objects.create(
            user=request.user,
            action='PASSWORD_CHANGE',
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            additional_data={
                'path': request.path,
                'method': request.method,
            }
        )

    def _handle_common_actions(self, request):
        """Gère les autres actions authentifiées"""
        action = self._determine_action(request)
        if action:
            UserActivityLog.objects.create(
                user=request.user,
                action=action,
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                additional_data={
                    'path': request.path,
                    'method': request.method,
                    'params': dict(request.GET) if request.method == 'GET' else {}
                }
            )

    def _determine_action(self, request):
        """Détermine l'action basée sur la requête"""
        path = request.path
        method = request.method

        # Table de correspondance URL -> Action
        action_map = {
            ('/api/auth/logout/', 'POST'): 'LOGOUT',
            ('/api/users/me/', 'PUT'): 'PROFILE_UPDATE',
            ('/api/users/me/', 'PATCH'): 'PROFILE_UPDATE',
            ('/api/users/me/', 'DELETE'): 'ACCOUNT_DELETION',
            ('/api/users/password/reset/', 'POST'): 'PASSWORD_RESET_REQUEST',
            ('/api/users/verify/', 'POST'): 'EMAIL_VERIFICATION',
        }

        return action_map.get((path, method))

    def _get_client_ip(self, request):
        """Récupère l'IP client de manière sécurisée"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip