"""Webhook Telegram Bot API — liaison contacts via /start <token>."""

from __future__ import annotations

import json
import logging

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .telegram_link import bind_chat_id
from .telegram_notify import send_message

logger = logging.getLogger(__name__)


def _check_secret(request: HttpRequest) -> bool:
    expected = (getattr(settings, "TELEGRAM_WEBHOOK_SECRET", None) or "").strip()
    if not expected:
        return True
    received = (request.headers.get("X-Telegram-Bot-Api-Secret-Token") or "").strip()
    return received == expected


def _extract_message(update: dict) -> dict | None:
    if "message" in update:
        return update["message"]
    if "edited_message" in update:
        return update["edited_message"]
    return None


def _handle_start(*, chat_id: str | int, text: str, contact_name: str = "") -> str:
    parts = (text or "").strip().split(maxsplit=1)
    token = parts[1].strip() if len(parts) > 1 else ""

    if not token:
        return (
            "👋 Bienvenue sur <b>Bokengi Alertes</b>.\n\n"
            "Pour recevoir les alertes SOS d'un proche, ouvrez le lien "
            "d'invitation qu'il vous a envoyé depuis l'app Bokengi."
        )

    contact = bind_chat_id(token=token, chat_id=chat_id)
    if not contact:
        return (
            "❌ Lien invalide ou expiré.\n"
            "Demandez à votre proche de générer un nouveau lien depuis Bokengi."
        )

    owner = contact.user.username or contact.user.email or "votre proche"
    return (
        f"✅ <b>Compte lié</b>\n\n"
        f"Vous recevrez les alertes SOS de <b>{owner}</b> "
        f"(contact : {contact.name})."
    )


@csrf_exempt
@require_http_methods(["POST"])
def telegram_webhook(request: HttpRequest) -> HttpResponse:
    """
    Webhook Telegram — configurer via :
    python manage.py telegram_test --set-webhook https://DOMAINE/api/webhooks/telegram/
    """
    if not _check_secret(request):
        logger.warning("Telegram webhook: secret token invalide")
        return HttpResponse(status=403)

    try:
        update = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponse(status=400)

    message = _extract_message(update)
    if not message:
        return JsonResponse({"ok": True})

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = message.get("text") or ""

    if not chat_id or not text.startswith("/"):
        return JsonResponse({"ok": True})

    reply = ""
    if text.startswith("/start"):
        reply = _handle_start(chat_id=chat_id, text=text)
    elif text.startswith("/help"):
        reply = (
            "<b>Bokengi Alertes</b>\n"
            "/start — lier votre compte via le lien d'invitation\n"
            "/help — cette aide"
        )
    else:
        reply = "Utilisez /help pour l'aide ou le lien d'invitation Bokengi."

    try:
        send_message(chat_id=chat_id, text=reply, parse_mode="HTML")
    except Exception:
        logger.exception("Impossible de répondre au chat_id=%s", chat_id)

    return JsonResponse({"ok": True})
