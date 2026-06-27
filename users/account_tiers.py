"""Forfaits citoyens (Normal / Pro / Premium) et contrôle d'accès."""

from __future__ import annotations

from rest_framework.permissions import BasePermission

NORMAL = "NORMAL"
PRO = "PRO"
PREMIUM = "PREMIUM"

ACCOUNT_TIER_CHOICES = [
    (NORMAL, "Normal"),
    (PRO, "Pro"),
    (PREMIUM, "Premium"),
]

TIER_RANK = {
    NORMAL: 0,
    PRO: 1,
    PREMIUM: 2,
}


def normalize_account_tier(value: str | None) -> str:
    if value in TIER_RANK:
        return value
    return NORMAL


def tier_at_least(user_tier: str | None, minimum: str) -> bool:
    return TIER_RANK.get(normalize_account_tier(user_tier), 0) >= TIER_RANK.get(
        normalize_account_tier(minimum), 0
    )


class MinCitizenTierPermission(BasePermission):
    """Bloque les citoyens dont le forfait est insuffisant (les admins passent toujours)."""

    message = "Cette fonctionnalité nécessite un forfait citoyen supérieur."

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        code = getattr(getattr(user, "type_user", None), "code_typeUser", None)
        if code == "ADMIN":
            return True
        if code != "USER":
            return False
        min_tier = getattr(view, "min_citizen_tier", PRO)
        return tier_at_least(getattr(user, "account_tier", NORMAL), min_tier)
