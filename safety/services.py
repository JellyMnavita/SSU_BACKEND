"""Utilitaires alignés sur l'app mobile Bokengi."""

MOBILE_SOURCE_TO_DB = {
    "citizen": "U",
    "authority": "U",
    "auto": "S",
    "sos": "O",
    "quick": "Q",
    "witness": "W",
}

DB_SOURCE_TO_MOBILE = {v: k for k, v in MOBILE_SOURCE_TO_DB.items() if k not in ("authority", "auto")}
DB_SOURCE_TO_MOBILE.setdefault("U", "citizen")
DB_SOURCE_TO_MOBILE.setdefault("C", "citizen")
DB_SOURCE_TO_MOBILE.setdefault("S", "auto")
DB_SOURCE_TO_MOBILE.setdefault("A", "authority")

MOBILE_DEGREE_TO_DB = {
    "low": "F",
    "faible": "F",
    "medium": "M",
    "moyen": "M",
    "high": "E",
    "eleve": "E",
    "élevé": "E",
    "F": "F",
    "M": "M",
    "E": "E",
}

DB_DEGREE_TO_MOBILE = {
    "F": "low",
    "M": "medium",
    "E": "high",
}


def user_can_trigger_sos(user) -> bool:
    """SOS réservé aux citoyens Premium (admins exemptés)."""
    code = getattr(getattr(user, "type_user", None), "code_typeUser", None)
    if code == "ADMIN":
        return True
    if code != "USER":
        return False
    from users.account_tiers import PREMIUM, tier_at_least

    return tier_at_least(getattr(user, "account_tier", "NORMAL"), PREMIUM)


_user_can_trigger_sos = user_can_trigger_sos


def map_mobile_degree(value: str) -> str:
    if not value:
        return "M"
    key = str(value).strip().lower()
    return MOBILE_DEGREE_TO_DB.get(key, MOBILE_DEGREE_TO_DB.get(value, "M"))


def map_mobile_source(value: str, *, is_witness: bool = False, is_sos: bool = False) -> str:
    if is_sos:
        return "O"
    if is_witness:
        return "W"
    if not value:
        return "U"
    return MOBILE_SOURCE_TO_DB.get(str(value).lower(), "U")
