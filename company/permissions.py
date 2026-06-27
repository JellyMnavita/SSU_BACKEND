from rest_framework.permissions import BasePermission


class IsCompanyUser(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and getattr(request.user.type_user, "code_typeUser", None) == "COMPANY"
        )
