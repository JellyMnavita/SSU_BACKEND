"""Limitation du débit pour la création de signalements (anti-spam)."""

from __future__ import annotations

from django.core.cache import cache
from django.utils import timezone

from users.session_utils import get_client_ip

BURST_LIMIT = 5
BURST_WINDOW_SECONDS = 5 * 60
DAILY_LIMIT_DEFAULT = 50
DAILY_LIMIT_GOV = 700

GOV_ROLE = "GOV"
ALLOWED_CREATOR_ROLES = frozenset({"ADMIN", "USER", GOV_ROLE})


class ReportRateLimitError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _try_consume(cache_key: str, limit: int, period_seconds: int) -> bool:
    count = cache.get(cache_key)
    if count is None:
        cache.set(cache_key, 1, period_seconds)
        return True
    if int(count) >= limit:
        return False
    try:
        new_count = cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, period_seconds)
        new_count = 1
    return int(new_count) <= limit


def _resolve_limits(request) -> tuple[str, str, int]:
    user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
    role = getattr(getattr(user, "type_user", None), "code_typeUser", None) if user else None

    if role == GOV_ROLE and user is not None:
        identifier = f"user:{user.pk}"
        return identifier, f"gov:{user.pk}", DAILY_LIMIT_GOV

    ip = get_client_ip(request) or "unknown"
    identifier = f"ip:{ip}"
    return identifier, identifier, DAILY_LIMIT_DEFAULT


def enforce_report_creation_limit(request) -> None:
    burst_id, daily_id, daily_limit = _resolve_limits(request)
    today = timezone.localdate().isoformat()

    burst_key = f"rl:report:burst:{burst_id}"
    daily_key = f"rl:report:daily:{daily_id}:{today}"

    if not _try_consume(burst_key, BURST_LIMIT, BURST_WINDOW_SECONDS):
        raise ReportRateLimitError("ERR_REPORT_RATE_LIMIT_BURST")

    if not _try_consume(daily_key, daily_limit, 90_000):
        raise ReportRateLimitError("ERR_REPORT_RATE_LIMIT_DAILY")
