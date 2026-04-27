from rest_framework.permissions import BasePermission

class RoleBasedAccess(BasePermission):
    """
    Permissions par type d'utilisateur :
    - ADMIN: Accès à tout (/admin/, /gov/, /company/, /user/, /citizen/)
    - GOV: Accès seulement aux URLs /gov/
    - COMPANY: Accès seulement aux URLs /company/
    - USER: Accès seulement aux URLs /user/
    - CITIZEN: Accès seulement aux URLs /citizen/
    """
    role_paths = {
        'ADMIN': ['/admin/', '/gov/', '/company/', '/user/', '/citizen/'],
        'GOV': ['/gov/'],
        'COMPANY': ['/company/'],
        'USER': ['/user/'],
        'CITIZEN': ['/citizen/']
    }

    def has_permission(self, request, view):
        user_type = request.user.type_user.code_typeUser
        allowed_paths = self.role_paths.get(user_type, [])
        return any(path in request.path for path in allowed_paths)
    
class IsAdminUserType(BasePermission):
    """
    Permission personnalisée qui vérifie que l'utilisateur est de type ADMIN
    """
    def has_permission(self, request, view):
        
        return (
            request.user.is_authenticated and 
            request.user.type_user.code_typeUser == 'ADMIN'
        )
        
class IsOwnerOrAdmin(BasePermission):
    """
    Permission personnalisée qui autorise :
    - Le propriétaire du compte
    - Les administrateurs
    """
    def has_object_permission(self, request, view, obj):
        return obj == request.user or request.user.type_user.code_typeUser == 'ADMIN'
    
class IsGovUser(BasePermission):
    def has_permission(self, request, view):
        return request.user.type_user.code_typeUser == 'GOV'
    
class IsAdminOrGov(BasePermission):
    """Vérifie que l'utilisateur est un administrateur ou un service gouvernemental"""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.type_user.code_typeUser in ['ADMIN', 'GOV']
        )