"""Catalogue de messages système FR / EN / Lingala."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from rest_framework import serializers

SUPPORTED_LANGS = ("fr", "en", "ln")
DEFAULT_LANG = "fr"

_current_lang: ContextVar[str] = ContextVar("ssu_lang", default=DEFAULT_LANG)

MESSAGES: dict[str, dict[str, str]] = {
    # Auth / utilisateurs
    "ERR_INVALID_CREDENTIALS": {
        "fr": "Identifiants invalides. Veuillez réessayer.",
        "en": "Invalid credentials. Please try again.",
        "ln": "Ba identifiants ezali malamu te. Meka lisusu.",
    },
    "ERR_ACCOUNT_NOT_VERIFIED": {
        "fr": "Votre compte n'est pas encore vérifié. Veuillez vérifier votre email.",
        "en": "Your account is not verified yet. Please check your email.",
        "ln": "Compte na yo evalidé naino te. Talá email na yo.",
    },
    "ERR_PASSWORD_UPPERCASE": {
        "fr": "Le mot de passe doit contenir au moins une majuscule.",
        "en": "Password must contain at least one uppercase letter.",
        "ln": "Mot de passe esengeli kozala na mokanda ya minene moko.",
    },
    "ERR_PASSWORD_SPECIAL": {
        "fr": "Le mot de passe doit contenir au moins un caractère spécial.",
        "en": "Password must contain at least one special character.",
        "ln": "Mot de passe esengeli kozala na caractère spécial moko.",
    },
    "ERR_PASSWORD_CONTAINS_USERNAME": {
        "fr": "Le mot de passe ne doit pas contenir votre nom d'utilisateur.",
        "en": "Password must not contain your username.",
        "ln": "Mot de passe esengeli kozanga kozala na nkombo na yo ya mosaleli.",
    },
    "ERR_USER_NOT_FOUND_EMAIL": {
        "fr": "Aucun utilisateur avec cet email n'a été trouvé.",
        "en": "No user found with this email.",
        "ln": "Mosaleli moko te na email oyo.",
    },
    "ERR_USER_NOT_FOUND": {
        "fr": "Aucun utilisateur avec cet email.",
        "en": "No user with this email.",
        "ln": "Mosaleli moko te na email oyo.",
    },
    "ERR_ALREADY_VERIFIED": {
        "fr": "Ce compte a déjà été vérifié.",
        "en": "This account has already been verified.",
        "ln": "Compte oyo evalidé déjà.",
    },
    "ERR_INVALID_VERIFICATION_CODE": {
        "fr": "Code de vérification incorrect.",
        "en": "Incorrect verification code.",
        "ln": "Code ya validation ezali malamu te.",
    },
    "ERR_VERIFICATION_CODE_EXPIRED": {
        "fr": "Le code de vérification a expiré.",
        "en": "The verification code has expired.",
        "ln": "Code ya validation esili ngonga.",
    },
    "ERR_EMAIL_ALREADY_USED": {
        "fr": "Cet email est déjà utilisé.",
        "en": "This email is already in use.",
        "ln": "Email oyo esalelaka déjà.",
    },
    "ERR_PASSWORDS_MISMATCH": {
        "fr": "Les mots de passe ne correspondent pas.",
        "en": "Passwords do not match.",
        "ln": "Ba mot de passe ekokani te.",
    },
    "ERR_ADMIN_PASSWORD_REQUIRED": {
        "fr": "Saisissez votre mot de passe administrateur pour confirmer.",
        "en": "Enter your administrator password to confirm.",
        "ln": "Kotia mot de passe na yo ya admin mpo na kondima.",
    },
    "ERR_ADMIN_PASSWORD_INVALID": {
        "fr": "Mot de passe administrateur incorrect.",
        "en": "Incorrect administrator password.",
        "ln": "Mot de passe ya admin ezali malamu te.",
    },
    "ERR_TIER_CITIZEN_ONLY": {
        "fr": "Le forfait ne s'applique qu'aux comptes citoyens (USER).",
        "en": "Tier applies only to citizen (USER) accounts.",
        "ln": "Forfait esalelaka kaka na ba compte ya citoyen (USER).",
    },
    "ERR_UNKNOWN_NOTIFICATION_KEYS": {
        "fr": "Clés inconnues : {keys}",
        "en": "Unknown keys: {keys}",
        "ln": "Ba clé oyo eyebani te : {keys}",
    },
    # Signalements
    "ERR_BIRTHDATE_REQUIRED": {
        "fr": "Date de naissance requise.",
        "en": "Birth date is required.",
        "ln": "Mokolo ya mbotama esengeli.",
    },
    "ERR_BIRTHDATE_FORMAT": {
        "fr": "Format de date de naissance invalide (YYYY-MM-DD).",
        "en": "Invalid birth date format (YYYY-MM-DD).",
        "ln": "Format ya mokolo ya mbotama ezali malamu te (YYYY-MM-DD).",
    },
    "ERR_BIRTHDATE_FUTURE": {
        "fr": "Date de naissance invalide (dans le futur).",
        "en": "Invalid birth date (in the future).",
        "ln": "Mokolo ya mbotama ezali malamu te (na nsima).",
    },
    "ERR_BIRTHDATE_TOO_YOUNG": {
        "fr": "Date de naissance invalide (âge trop faible).",
        "en": "Invalid birth date (age too young).",
        "ln": "Mokolo ya mbotama ezali malamu te (moke mingi).",
    },
    "ERR_BIRTHDATE_TOO_OLD": {
        "fr": "Date de naissance invalide (âge trop élevé).",
        "en": "Invalid birth date (age too high).",
        "ln": "Mokolo ya mbotama ezali malamu te (monene mingi).",
    },
    "ERR_IMAGE_FORMAT": {
        "fr": "Format d'image non supporté",
        "en": "Unsupported image format",
        "ln": "Format ya elilingi esungami te",
    },
    "ERR_INVALID_GPS": {
        "fr": "Coordonnées GPS invalides",
        "en": "Invalid GPS coordinates",
        "ln": "Ba coordonnées GPS ezali malamu te",
    },
    "ERR_CITIZEN_INFO_REQUIRED": {
        "fr": "Toutes les informations citoyen sont requises",
        "en": "All citizen information is required",
        "ln": "Ba info ya citoyen nyonso esengeli",
    },
    "ERR_SOURCE_NOT_ALLOWED": {
        "fr": "Source non autorisée",
        "en": "Source not allowed",
        "ln": "Source endimami te",
    },
    "ERR_VERIFIED_REPORT_LOCKED": {
        "fr": "Un signalement vérifié ne peut plus être modifié.",
        "en": "A verified report can no longer be modified.",
        "ln": "Signalement oyo evalidé ekoki kobongisama lisusu te.",
    },
    # Géolocalisation
    "ERR_KINSHASA_ONLY": {
        "fr": "Les signalements et alertes ne sont autorisés qu'à Kinshasa (RDC).",
        "en": "Reports and alerts are only allowed within Kinshasa (DRC).",
        "ln": "Bisango mpe ba alerte endimami kaka na Kinshasa (RDC).",
    },
    "ERR_WATER_ZONE": {
        "fr": "Les coordonnées pointent vers le fleuve Congo ou une zone d'eau — signalement non accepté.",
        "en": "Coordinates point to the Congo River or a water area — report not accepted.",
        "ln": "Ba coordonnées ezali na moluka Congo to esika ya mai — signalement endimami te.",
    },
    "ERR_INCONSISTENT_LOCATION": {
        "fr": "Les coordonnées GPS ne correspondent pas au lieu indiqué dans Kinshasa. Vérifiez la position sur la carte.",
        "en": "GPS coordinates do not match the indicated location in Kinshasa. Check the position on the map.",
        "ln": "Ba coordonnées GPS ekokani te na esika oyo olobi na Kinshasa. Talá esika na karte.",
    },
    # Sécurité / SOS
    "ERR_MAX_TRUSTED_CONTACTS": {
        "fr": "Maximum {max} contacts de confiance.",
        "en": "Maximum {max} trusted contacts.",
        "ln": "Maximum {max} ba contact ya confiance.",
    },
    # Paramètres IA
    "ERR_THRESHOLD_RANGE": {
        "fr": "Le seuil doit être entre 0 et 1.",
        "en": "Threshold must be between 0 and 1.",
        "ln": "Seuil esengeli kozala kati ya 0 na 1.",
    },
    # Entreprise
    "ERR_COMPANY_SITE_REQUIRED": {
        "fr": "Au moins un site est requis pour ce compte entreprise.",
        "en": "At least one site is required for this company account.",
        "ln": "Esika moko to koleka esengeli mpo na compte entreprise oyo.",
    },
    "ERR_RADIUS_RANGE": {
        "fr": "Le rayon doit être entre 200 m et 10 km.",
        "en": "Radius must be between 200 m and 10 km.",
        "ln": "Rayon esengeli kozala kati ya 200 m na 10 km.",
    },
    "ERR_MAX_SITES": {
        "fr": "Maximum {max} sites par organisation.",
        "en": "Maximum {max} sites per organization.",
        "ln": "Maximum {max} ba site na organisation.",
    },
    "ERR_IMAGE_TOO_LARGE": {
        "fr": "La taille de l'image ne doit pas dépasser 5 Mo.",
        "en": "Image size must not exceed 5 MB.",
        "ln": "Bonene ya elilingi esengeli koleka 5 Mo te.",
    },
    "ERR_IMAGE_DUPLICATE": {
        "fr": "Cette image a déjà été utilisée pour un signalement.",
        "en": "This image has already been used for a report.",
        "ln": "Elilingi oyo esalelaki déjà mpo na signalement.",
    },
    "ERR_REPORT_ROLE_ONLY": {
        "fr": "Seuls les administrateurs, citoyens et services gouvernementaux peuvent créer des signalements.",
        "en": "Only administrators, citizens and government accounts can create reports.",
        "ln": "Kaka administrateur, citoyen mpe gouvernement bakoki kosala ba signalement.",
    },
    "ERR_REPORT_RATE_LIMIT_BURST": {
        "fr": "Trop de signalements en peu de temps. Réessayez dans quelques minutes.",
        "en": "Too many reports in a short time. Try again in a few minutes.",
        "ln": "Bisango ebele mingi na ntango mokuse. Meka lisusu na miniti moke.",
    },
    "ERR_REPORT_RATE_LIMIT_DAILY": {
        "fr": "Limite journalière de signalements atteinte. Réessayez demain.",
        "en": "Daily report limit reached. Try again tomorrow.",
        "ln": "Limite ya mokolo esili. Meka lisusu lobi.",
    },
    "ERR_INVALID_QUARTIER": {
        "fr": "Quartier invalide pour le citoyen.",
        "en": "Invalid neighborhood for the citizen.",
        "ln": "Quartier ezali malamu te mpo na citoyen.",
    },
    "ERR_INVALID_JSON": {
        "fr": "Format JSON invalide pour citizen_data.",
        "en": "Invalid JSON format for citizen_data.",
        "ln": "Format JSON ezali malamu te mpo na citizen_data.",
    },
    "ERR_INVALID_THEME": {
        "fr": "Thème invalide. Valeurs : {values}.",
        "en": "Invalid theme. Values: {values}.",
        "ln": "Thème ezali malamu te. Ba valeur : {values}.",
    },
}


def normalize_lang(lang: str | None) -> str:
    if not lang:
        return DEFAULT_LANG
    code = lang.strip().lower().split("-")[0]
    if code in ("ln", "lingala"):
        return "ln"
    if code.startswith("en"):
        return "en"
    if code.startswith("fr"):
        return "fr"
    return DEFAULT_LANG


def get_lang_from_request(request) -> str:
    if request is None:
        return current_lang()
    accept = request.META.get("HTTP_ACCEPT_LANGUAGE", "")
    for part in accept.split(","):
        token = part.strip().split(";")[0].strip().lower()
        if token.startswith("ln") or token == "lingala":
            return "ln"
        if token.startswith("en"):
            return "en"
        if token.startswith("fr"):
            return "fr"
    return DEFAULT_LANG


def set_current_lang(lang: str) -> None:
    _current_lang.set(normalize_lang(lang))


def current_lang() -> str:
    return _current_lang.get()


def translate(code: str, lang: str | None = None, **kwargs: Any) -> str:
    normalized = normalize_lang(lang or current_lang())
    entry = MESSAGES.get(code)
    if not entry:
        return code
    message = entry.get(normalized) or entry.get("fr") or code
    if kwargs:
        try:
            return message.format(**kwargs)
        except (KeyError, ValueError):
            return message
    return message


def validation_error(
    code: str,
    context: dict | None = None,
    field: str | None = None,
    **kwargs: Any,
) -> serializers.ValidationError:
    request = (context or {}).get("request")
    lang = get_lang_from_request(request) if request else current_lang()
    message = translate(code, lang=lang, **kwargs)
    if field:
        return serializers.ValidationError({field: message})
    return serializers.ValidationError(message)


def drf_validation_error(
    code: str,
    request=None,
    field: str | None = None,
    **kwargs: Any,
) -> ValidationError:
    """Pour les vues API sans serializer context."""
    from rest_framework.exceptions import ValidationError

    lang = get_lang_from_request(request) if request else current_lang()
    message = translate(code, lang=lang, **kwargs)
    if field:
        raise ValidationError({field: message})
    raise ValidationError(message)
