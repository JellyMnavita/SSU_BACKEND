"""Webhook Twilio WhatsApp — statuts de livraison + messages entrants."""

from __future__ import annotations

import logging

from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def twilio_whatsapp_webhook(request: HttpRequest) -> HttpResponse:
    """
    Status callback / inbound WhatsApp.
    Configurer dans Twilio Console → WhatsApp sandbox / sender → webhook URL :
    https://VOTRE_DOMAINE/api/webhooks/twilio/whatsapp/
    """
    message_sid = request.POST.get("MessageSid") or request.POST.get("SmsSid")
    status = request.POST.get("MessageStatus") or request.POST.get("SmsStatus")
    from_number = request.POST.get("From", "")
    to_number = request.POST.get("To", "")
    body = request.POST.get("Body", "")

    if status:
        logger.info(
            "Twilio WhatsApp status sid=%s status=%s from=%s to=%s",
            message_sid,
            status,
            from_number,
            to_number,
        )
    if body:
        logger.info(
            "Twilio WhatsApp inbound from=%s body=%s",
            from_number,
            body[:200],
        )

    # Twilio attend un 200 (TwiML vide OK)
    return HttpResponse(
        '<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        content_type="text/xml",
    )
