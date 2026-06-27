from __future__ import annotations

from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from .models import UserSession


def get_client_ip(request) -> str | None:
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def get_refresh_jti(request) -> str | None:
    refresh_token = request.COOKIES.get("refresh_token")
    if not refresh_token:
        return None
    try:
        token = RefreshToken(refresh_token)
        return str(token.get("jti"))
    except TokenError:
        return None


def cleanup_stale_sessions(user) -> None:
    """Supprime les entrées UserSession dont le refresh token n'est plus actif."""
    blacklisted_jtis = set(
        BlacklistedToken.objects.filter(token__user=user).values_list("token__jti", flat=True)
    )
    active_jtis = set(
        OutstandingToken.objects.filter(user=user)
        .exclude(jti__in=blacklisted_jtis)
        .values_list("jti", flat=True)
    )
    UserSession.objects.filter(user=user).exclude(jti__in=active_jtis).delete()


def register_user_session(user, jti: str, request) -> None:
    user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:255]
    ip_address = get_client_ip(request)

    cleanup_stale_sessions(user)

    # Un seul enregistrement par navigateur (évite la multiplication sur le même PC).
    if user_agent:
        UserSession.objects.filter(user=user, user_agent=user_agent).exclude(jti=jti).delete()

    UserSession.objects.update_or_create(
        jti=jti,
        defaults={
            "user": user,
            "user_agent": user_agent,
            "ip_address": ip_address,
        },
    )


def remove_user_session(user, jti: str | None) -> None:
    if not jti:
        return
    UserSession.objects.filter(user=user, jti=jti).delete()


def list_active_sessions(user, current_jti: str | None = None) -> list[dict]:
    cleanup_stale_sessions(user)
    blacklisted_jtis = set(
        BlacklistedToken.objects.filter(token__user=user).values_list("token__jti", flat=True)
    )
    active_tokens = {
        ot.jti: ot
        for ot in OutstandingToken.objects.filter(user=user).exclude(jti__in=blacklisted_jtis)
    }

    sessions = []
    for session in UserSession.objects.filter(user=user, jti__in=active_tokens.keys()).order_by(
        "-created_at"
    ):
        token = active_tokens.get(session.jti)
        sessions.append(
            {
                "jti": session.jti,
                "user_agent": session.user_agent,
                "ip_address": session.ip_address,
                "created_at": session.created_at,
                "expires_at": token.expires_at if token else None,
                "is_current": session.jti == current_jti,
            }
        )
    return sessions


def revoke_session(user, jti: str, current_jti: str | None = None) -> bool:
    if current_jti and jti == current_jti:
        return False

    try:
        outstanding = OutstandingToken.objects.get(user=user, jti=jti)
        RefreshToken(outstanding.token).blacklist()
    except OutstandingToken.DoesNotExist:
        pass

    UserSession.objects.filter(user=user, jti=jti).delete()
    return True


def revoke_other_sessions(user, keep_jti: str | None) -> int:
    revoked = 0
    blacklisted_jtis = set(
        BlacklistedToken.objects.filter(token__user=user).values_list("token__jti", flat=True)
    )
    for outstanding in OutstandingToken.objects.filter(user=user).exclude(jti__in=blacklisted_jtis):
        if keep_jti and outstanding.jti == keep_jti:
            continue
        try:
            RefreshToken(outstanding.token).blacklist()
            revoked += 1
        except TokenError:
            continue
        UserSession.objects.filter(user=user, jti=outstanding.jti).delete()
    return revoked
