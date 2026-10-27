"""Envoi WhatsApp via Twilio Messaging API."""

from __future__ import annotations

import json
import logging
import re

from django.conf import settings

logger = logging.getLogger(__name__)


class TwilioWhatsAppError(Exception):
    pass


def is_enabled() -> bool:
    if not getattr(settings, "TWILIO_WHATSAPP_ENABLED", False):
        return False
    sid = (getattr(settings, "TWILIO_ACCOUNT_SID", None) or "").strip()
    token = (getattr(settings, "TWILIO_AUTH_TOKEN", None) or "").strip()
    from_number = (getattr(settings, "TWILIO_WHATSAPP_FROM", None) or "").strip()
    return bool(sid and token and from_number)


def _e164(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        return ""
    if digits.startswith("243"):
        return f"+{digits}"
    if digits.startswith("0") and len(digits) >= 9:
        return f"+243{digits[1:]}"
    if digits.startswith("00"):
        return f"+{digits[2:]}"
    if not digits.startswith("+"):
        return f"+{digits}"
    return digits


def _whatsapp_address(phone: str) -> str:
    e164 = _e164(phone)
    if not e164:
        raise TwilioWhatsAppError("Numéro destinataire invalide")
    if e164.startswith("whatsapp:"):
        return e164
    return f"whatsapp:{e164}"


def _from_address() -> str:
    raw = (getattr(settings, "TWILIO_WHATSAPP_FROM", None) or "").strip()
    if not raw:
        raise TwilioWhatsAppError("TWILIO_WHATSAPP_FROM manquant")
    if raw.startswith("whatsapp:"):
        return raw
    if raw.startswith("+"):
        return f"whatsapp:{raw}"
    digits = re.sub(r"\D", "", raw)
    return f"whatsapp:+{digits}"


def _client():
    try:
        from twilio.rest import Client
    except ImportError as exc:
        raise TwilioWhatsAppError(
            "Package twilio non installé (pip install twilio)"
        ) from exc

    sid = (getattr(settings, "TWILIO_ACCOUNT_SID", None) or "").strip()
    token = (getattr(settings, "TWILIO_AUTH_TOKEN", None) or "").strip()
    if not sid or not token:
        raise TwilioWhatsAppError("TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN manquants")
    return Client(sid, token)


def send_whatsapp_text(*, to_phone: str, body: str) -> str:
    """Envoi free-form (sandbox Twilio ou fenêtre 24 h Meta)."""
    if not is_enabled():
        raise TwilioWhatsAppError("Twilio WhatsApp désactivé")
    client = _client()
    message = client.messages.create(
        from_=_from_address(),
        to=_whatsapp_address(to_phone),
        body=body,
    )
    logger.info("Twilio WhatsApp text sid=%s to=%s", message.sid, to_phone)
    return message.sid


def send_whatsapp_template(
    *,
    to_phone: str,
    content_sid: str,
    variables: dict[str, str] | None = None,
) -> str:
    """Envoi template Content API (requis pour SOS hors fenêtre 24 h)."""
    if not is_enabled():
        raise TwilioWhatsAppError("Twilio WhatsApp désactivé")
    if not content_sid:
        raise TwilioWhatsAppError("content_sid manquant")
    client = _client()
    kwargs = {
        "from_": _from_address(),
        "to": _whatsapp_address(to_phone),
        "content_sid": content_sid,
    }
    if variables:
        kwargs["content_variables"] = json.dumps(variables)
    message = client.messages.create(**kwargs)
    logger.info(
        "Twilio WhatsApp template sid=%s content=%s to=%s",
        message.sid,
        content_sid,
        to_phone,
    )
    return message.sid


def send_safety_alert(
    *,
    to_phone: str,
    kind: str,
    contact_name: str,
    initiator_name: str,
    track_url: str,
    extra: dict | None = None,
) -> bool:
    """
    Envoie une alerte sécurité WhatsApp.
    Préfère un template Content SID si configuré, sinon message texte (sandbox).
    """
    if not is_enabled() or not to_phone:
        return False

    extra = extra or {}
    template_map = {
        "sos": getattr(settings, "TWILIO_WA_TEMPLATE_SOS", "") or "",
        "trip": getattr(settings, "TWILIO_WA_TEMPLATE_TRIP", "") or "",
        "checkin": getattr(settings, "TWILIO_WA_TEMPLATE_CHECKIN", "") or "",
        "checkin_missed": getattr(settings, "TWILIO_WA_TEMPLATE_CHECKIN_MISSED", "") or "",
    }
    content_sid = (template_map.get(kind) or "").strip()

    try:
        if content_sid:
            variables = {
                "1": contact_name or "Contact",
                "2": initiator_name or "Un proche",
                "3": track_url,
            }
            if kind == "trip" and extra.get("dest_label"):
                variables["4"] = str(extra["dest_label"])
            if kind == "checkin" and extra.get("duration_minutes"):
                variables["4"] = str(extra["duration_minutes"])
            send_whatsapp_template(
                to_phone=to_phone,
                content_sid=content_sid,
                variables=variables,
            )
            return True

        # Fallback texte (sandbox / fenêtre 24h)
        bodies = {
            "sos": (
                f"🚨 SOS Bokengi\nBonjour {contact_name},\n"
                f"{initiator_name} a déclenché une alerte SOS.\n"
                f"Suivi en direct : {track_url}"
            ),
            "trip": (
                f"📍 Trajet Bokengi\nBonjour {contact_name},\n"
                f"{initiator_name} partage son trajet"
                f"{(' vers ' + str(extra['dest_label'])) if extra.get('dest_label') else ''}.\n"
                f"Suivi : {track_url}"
            ),
            "checkin": (
                f"✅ Check-in Bokengi\nBonjour {contact_name},\n"
                f"{initiator_name} a démarré un check-in sécurité"
                f"{(f' ({extra['duration_minutes']} min)') if extra.get('duration_minutes') else ''}.\n"
                f"Suivi : {track_url}"
            ),
            "checkin_missed": (
                f"⚠️ Check-in manqué\nBonjour {contact_name},\n"
                f"{initiator_name} n'a pas confirmé son check-in à temps.\n"
                f"Suivi : {track_url}"
            ),
        }
        body = bodies.get(kind) or (
            f"Alerte Bokengi de {initiator_name}.\nSuivi : {track_url}"
        )
        send_whatsapp_text(to_phone=to_phone, body=body)
        return True
    except Exception:
        logger.exception("Échec WhatsApp Twilio vers %s (kind=%s)", to_phone, kind)
        return False
