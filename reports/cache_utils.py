"""Invalidation du cache liste signalements après enrichissement IA."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def invalidate_reports_list_cache() -> None:
    try:
        from django_redis import get_redis_connection

        conn = get_redis_connection("default")
        # Selon les versions, l'objet de connexion peut ne pas exposer make_key().
        # On invalide alors par pattern brut.
        try:
            prefix = conn.make_key("reports:list:")
        except Exception:
            prefix = "reports:list:"

        for key in conn.scan_iter(match=f"{prefix}*"):
            conn.delete(key)
    except Exception as exc:
        logger.warning("Could not invalidate reports list cache: %s", exc)
