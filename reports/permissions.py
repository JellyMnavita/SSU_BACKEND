from rest_framework import permissions
from django.contrib.auth import get_user_model

User = get_user_model()

class IsGovernment(permissions.BasePermission):
    """Vérifie que l'utilisateur est un service gouvernemental"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.type_user.code_typeUser == 'GOV'

class IsCompany(permissions.BasePermission):
    """Vérifie que l'utilisateur est une entreprise étrangère"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.type_user.code_typeUser == 'COMPANY'

class IsAdmin(permissions.BasePermission):
    """Vérifie que l'utilisateur est un administrateur"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.type_user.code_typeUser == 'ADMIN'

class IsSimpleUser(permissions.BasePermission):
    """Vérifie que l'utilisateur est un utilisateur simple"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.type_user.code_typeUser == 'USER'

class IsOwnerOrAdmin(permissions.BasePermission):
    """Autorise le propriétaire ou l'admin"""
    def has_object_permission(self, request, view, obj):
        if request.user.is_authenticated and request.user.type_user.code_typeUser == 'ADMIN':
            return True
            
        if hasattr(obj, 'user'):
            return obj.user == request.user
            
        if hasattr(obj, 'citizen'):
            return request.data.get('email') == obj.citizen.email
            
        return False

class CanCreateReport(permissions.BasePermission):
    """Vérifie les permissions de création selon le type d'utilisateur"""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            # Permet la création pour les citoyens non-inscrits
            return view.action == 'citizen_report'
            
        user_type = request.user.type_user.code_typeUser
        return user_type in ['CITIZEN', 'GOV', 'COMPANY', 'ADMIN', 'USER']

class IsAdminOrGov(permissions.BasePermission):
    """Vérifie que l'utilisateur est un administrateur ou un service gouvernemental"""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.type_user.code_typeUser in ['ADMIN', 'GOV']
        )