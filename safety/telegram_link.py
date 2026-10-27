"""Liaison contact de confiance ↔ compte Telegram via /start <token>."""

from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import TrustedContact
from .telegram_notify import TelegramNotifyError, get_bot_info


LINK_TOKEN_TTL_DAYS = 7


def _bot_username() -> str:
    configured = (getattr(settings, "TELEGRAM_BOT_USERNAME", None) or "").strip().lstrip("@")
    if configured:
        return configured
    try:
        info = get_bot_info()
    except TelegramNotifyError:
        return ""
    return (info.get("username") or "").strip()


def create_link_for_contact(contact: TrustedContact) -> dict:
    """
    Génère un token court (≤64 car. pour deep link Telegram) et l'URL d'invitation.
    """
    token = secrets.token_urlsafe(16).replace("-", "").replace("_", "")[:20]
    expires_at = timezone.now() + timedelta(days=LINK_TOKEN_TTL_DAYS)

    contact.telegram_link_token = token
    contact.telegram_link_expires_at = expires_at
    contact.save(
        update_fields=["telegram_link_token", "telegram_link_expires_at", "updated_at"]
    )

    username = _bot_username()
    link_url = f"https://t.me/{username}?start={token}" if username else ""
    return {
        "token": token,
        "link_url": link_url,
        "expires_at": expires_at,
        "bot_username": username,
        "telegram_linked": bool(contact.telegram_chat_id),
    }


def bind_chat_id(*, token: str, chat_id: str | int) -> TrustedContact | None:
    """Associe un chat_id Telegram au contact correspondant au token."""
    clean_token = (token or "").strip()
    if not clean_token:
        return None

    contact = (
        TrustedContact.objects.filter(telegram_link_token=clean_token)
        .select_related("user")
        .first()
    )
    if not contact:
        return None

    if contact.telegram_link_expires_at and contact.telegram_link_expires_at < timezone.now():
        return None

    contact.telegram_chat_id = str(chat_id)
    contact.telegram_link_token = ""
    contact.telegram_link_expires_at = None
    contact.save(
        update_fields=[
            "telegram_chat_id",
            "telegram_link_token",
            "telegram_link_expires_at",
            "updated_at",
        ]
    )
    return contact


def unlink_contact(contact: TrustedContact) -> None:
    contact.telegram_chat_id = ""
    contact.telegram_link_token = ""
    contact.telegram_link_expires_at = None
    contact.save(
        update_fields=[
            "telegram_chat_id",
            "telegram_link_token",
            "telegram_link_expires_at",
            "updated_at",
        ]
    )
