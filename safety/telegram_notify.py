"""Envoi d'alertes sécurité via Telegram Bot API."""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

# Image visuelle jointe aux alertes (SOS, trajet, check-in…).
_ALERT_IMAGE = (
    Path(__file__).resolve().parent.parent / "static" / "alerts" / "urgence_bokengi.png"
)


class TelegramNotifyError(Exception):
    pass


def is_enabled() -> bool:
    if not getattr(settings, "TELEGRAM_ENABLED", False):
        return False
    token = (getattr(settings, "TELEGRAM_BOT_TOKEN", None) or "").strip()
    return bool(token)


def _api_url(method: str) -> str:
    token = (getattr(settings, "TELEGRAM_BOT_TOKEN", None) or "").strip()
    if not token:
        raise TelegramNotifyError("TELEGRAM_BOT_TOKEN manquant")
    return f"https://api.telegram.org/bot{token}/{method}"


def _request(method: str, *, json_payload: dict | None = None) -> dict:
    url = _api_url(method)
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(url, json=json_payload or {})
    except httpx.HTTPError as exc:
        raise TelegramNotifyError(f"Erreur réseau Telegram: {exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise TelegramNotifyError(
            f"Réponse Telegram invalide (HTTP {response.status_code})"
        ) from exc

    if not data.get("ok"):
        description = data.get("description") or response.text
        raise TelegramNotifyError(f"Telegram API: {description}")
    return data


def get_bot_info() -> dict:
    """Retourne les infos du bot (getMe)."""
    data = _request("getMe")
    return data.get("result") or {}


def set_webhook(*, url: str, secret_token: str = "") -> dict:
    payload: dict = {"url": url}
    secret = (secret_token or "").strip()
    if secret:
        payload["secret_token"] = secret
    data = _request("setWebhook", json_payload=payload)
    return data.get("result") or {}


def send_message(*, chat_id: str | int, text: str, parse_mode: str = "") -> int:
    if not is_enabled():
        raise TelegramNotifyError("Telegram désactivé")
    if not chat_id:
        raise TelegramNotifyError("chat_id manquant")

    payload: dict = {
        "chat_id": str(chat_id),
        "text": text,
        "disable_web_page_preview": False,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    data = _request("sendMessage", json_payload=payload)
    result = data.get("result") or {}
    message_id = result.get("message_id")
    logger.info("Telegram message id=%s chat_id=%s", message_id, chat_id)
    return int(message_id or 0)


def send_photo(
    *,
    chat_id: str | int,
    photo_path: Path | str,
    caption: str = "",
    parse_mode: str = "",
) -> int:
    """Envoie une photo avec légende (multipart)."""
    if not is_enabled():
        raise TelegramNotifyError("Telegram désactivé")
    if not chat_id:
        raise TelegramNotifyError("chat_id manquant")

    path = Path(photo_path)
    if not path.is_file():
        raise TelegramNotifyError(f"Image introuvable: {path}")

    url = _api_url("sendPhoto")
    data: dict = {"chat_id": str(chat_id)}
    if caption:
        data["caption"] = caption[:1024]
    if parse_mode:
        data["parse_mode"] = parse_mode

    try:
        with path.open("rb") as photo_file:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    url,
                    data=data,
                    files={"photo": (path.name, photo_file, "image/png")},
                )
    except httpx.HTTPError as exc:
        raise TelegramNotifyError(f"Erreur réseau Telegram: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise TelegramNotifyError(
            f"Réponse Telegram invalide (HTTP {response.status_code})"
        ) from exc

    if not payload.get("ok"):
        description = payload.get("description") or response.text
        raise TelegramNotifyError(f"Telegram API: {description}")

    result = payload.get("result") or {}
    message_id = result.get("message_id")
    logger.info("Telegram photo id=%s chat_id=%s", message_id, chat_id)
    return int(message_id or 0)


def send_safety_alert(
    *,
    chat_id: str,
    kind: str,
    contact_name: str,
    initiator_name: str,
    track_url: str,
    extra: dict | None = None,
) -> bool:
    """Envoie une alerte sécurité (photo + légende) à un contact Telegram lié."""
    if not is_enabled() or not chat_id:
        return False

    extra = extra or {}
    bodies = {
        "sos": (
            f"🚨 <b>APPEL D'URGENCE — SOS Bokengi</b>\n"
            f"Bonjour {contact_name},\n"
            f"{initiator_name} a déclenché une alerte SOS.\n"
            f"Incident signalé. Besoin d'assistance immédiate.\n"
            f"Suivi en direct : {track_url}"
        ),
        "trip": (
            f"📍 <b>Trajet Bokengi</b>\n"
            f"Bonjour {contact_name},\n"
            f"{initiator_name} partage son trajet"
            f"{(' vers ' + str(extra['dest_label'])) if extra.get('dest_label') else ''}.\n"
            f"Suivi : {track_url}"
        ),
        "checkin": (
            f"✅ <b>Check-in Bokengi</b>\n"
            f"Bonjour {contact_name},\n"
            f"{initiator_name} a démarré un check-in sécurité"
            f"{(f' ({extra['duration_minutes']} min)') if extra.get('duration_minutes') else ''}.\n"
            f"Suivi : {track_url}"
        ),
        "checkin_missed": (
            f"⚠️ <b>Check-in manqué</b>\n"
            f"Bonjour {contact_name},\n"
            f"{initiator_name} n'a pas confirmé son check-in à temps.\n"
            f"Suivi : {track_url}"
        ),
    }
    body = bodies.get(kind) or (
        f"<b>Alerte Bokengi</b> de {initiator_name}.\nSuivi : {track_url}"
    )

    try:
        if _ALERT_IMAGE.is_file():
            send_photo(
                chat_id=chat_id,
                photo_path=_ALERT_IMAGE,
                caption=body,
                parse_mode="HTML",
            )
        else:
            logger.warning("Image alerte absente (%s) — envoi texte seul", _ALERT_IMAGE)
            send_message(chat_id=chat_id, text=body, parse_mode="HTML")
        return True
    except Exception:
        logger.exception("Échec Telegram vers chat_id=%s (kind=%s)", chat_id, kind)
        return False
