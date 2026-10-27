"""Webhook WhatsApp Cloud API (Meta) — vérification + réception des événements."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)


def _verify_signature(request: HttpRequest) -> bool:
    """Valide X-Hub-Signature-256 si WHATSAPP_APP_SECRET est configuré."""
    secret = (getattr(settings, "WHATSAPP_APP_SECRET", None) or "").strip()
    if not secret:
        return True

    header = request.headers.get("X-Hub-Signature-256", "")
    if not header.startswith("sha256="):
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        request.body,
        hashlib.sha256,
    ).hexdigest()
    received = header[7:]
    return hmac.compare_digest(expected, received)


def _handle_verification(request: HttpRequest) -> HttpResponse:
    mode = request.GET.get("hub.mode")
    token = request.GET.get("hub.verify_token")
    challenge = request.GET.get("hub.challenge")
    verify_token = (getattr(settings, "WHATSAPP_VERIFY_TOKEN", None) or "").strip()

    if not verify_token:
        logger.error(
            "WHATSAPP_VERIFY_TOKEN non configuré — impossible de valider le webhook Meta."
        )
        return HttpResponse("Verify token not configured", status=503)

    if mode == "subscribe" and token == verify_token and challenge:
        logger.info("Webhook WhatsApp vérifié avec succès.")
        return HttpResponse(challenge, content_type="text/plain")

    logger.warning(
        "Échec vérification webhook WhatsApp (mode=%s, token_invalide=%s).",
        mode,
        token != verify_token,
    )
    return HttpResponse("Forbidden", status=403)


def _log_webhook_payload(payload: dict) -> None:
    """Journalise les événements utiles (messages, statuts, templates)."""
    if payload.get("object") != "whatsapp_business_account":
        logger.debug("Webhook WhatsApp ignoré: object=%s", payload.get("object"))
        return

    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            field = change.get("field")
            value = change.get("value") or {}

            for status in value.get("statuses") or []:
                logger.info(
                    "WhatsApp statut message id=%s status=%s recipient=%s",
                    status.get("id"),
                    status.get("status"),
                    status.get("recipient_id"),
                )

            for message in value.get("messages") or []:
                msg_type = message.get("type")
                sender = message.get("from")
                if msg_type == "text":
                    body = (message.get("text") or {}).get("body", "")
                    logger.info("WhatsApp message entrant de %s: %s", sender, body[:200])
                else:
                    logger.info(
                        "WhatsApp message entrant de %s (type=%s)",
                        sender,
                        msg_type,
                    )

            if field == "message_template_status_update":
                event = value.get("event")
                template = (value.get("message_template_name") or value.get("name") or "?")
                logger.info("WhatsApp template %s — event=%s", template, event)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def whatsapp_webhook(request: HttpRequest) -> HttpResponse:
    """
    GET  — vérification Meta (hub.mode=subscribe).
    POST — notifications messages / statuts / templates.
    """
    if request.method == "GET":
        return _handle_verification(request)

    if not _verify_signature(request):
        logger.warning("Signature webhook WhatsApp invalide.")
        return HttpResponse("Invalid signature", status=403)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.exception("Corps webhook WhatsApp illisible.")
        return HttpResponse("Bad Request", status=400)

    _log_webhook_payload(payload)
    return HttpResponse("EVENT_RECEIVED", content_type="text/plain", status=200)
