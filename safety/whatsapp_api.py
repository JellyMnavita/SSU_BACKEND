"""Client minimal WhatsApp Cloud API (Meta Graph)."""

from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class WhatsAppApiError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def _api_version() -> str:
    return (getattr(settings, "WHATSAPP_API_VERSION", None) or "v23.0").strip()


def _access_token() -> str:
    token = (getattr(settings, "WHATSAPP_ACCESS_TOKEN", None) or "").strip()
    if not token:
        raise WhatsAppApiError(
            "WHATSAPP_ACCESS_TOKEN manquant dans ssu_backend/.env"
        )
    return token


def _graph_url(path: str) -> str:
    version = _api_version()
    clean = path.lstrip("/")
    return f"https://graph.facebook.com/{version}/{clean}"


def _request(method: str, path: str, *, json_body: dict | None = None) -> dict:
    response = requests.request(
        method,
        _graph_url(path),
        headers={
            "Authorization": f"Bearer {_access_token()}",
            "Content-Type": "application/json",
        },
        json=json_body,
        timeout=30,
    )
    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text}

    if not response.ok:
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        message = error.get("message") if isinstance(error, dict) else str(payload)
        raise WhatsAppApiError(
            message or f"Erreur WhatsApp API HTTP {response.status_code}",
            status_code=response.status_code,
            payload=payload,
        )
    return payload if isinstance(payload, dict) else {"data": payload}


def list_phone_numbers(waba_id: str | None = None) -> list[dict]:
    """Liste les numéros du compte WhatsApp Business."""
    account_id = (waba_id or getattr(settings, "WHATSAPP_BUSINESS_ACCOUNT_ID", None) or "").strip()
    if not account_id:
        raise WhatsAppApiError("WHATSAPP_BUSINESS_ACCOUNT_ID manquant dans .env")
    data = _request("GET", f"{account_id}/phone_numbers")
    return data.get("data") or []


def register_phone_number(*, phone_number_id: str, pin: str) -> dict:
    """
    Finalise l'enregistrement Cloud API d'un numéro vérifié (statut « En attente »).
    Le PIN est un code à 6 chiffres que VOUS choisissez (2FA WhatsApp Business),
    pas le code SMS de vérification déjà saisi.
    """
    pid = phone_number_id.strip()
    pin_value = pin.strip()
    if len(pid) < 5:
        raise WhatsAppApiError("phone_number_id invalide")
    if not pin_value.isdigit() or len(pin_value) != 6:
        raise WhatsAppApiError("Le PIN doit contenir exactement 6 chiffres")

    return _request(
        "POST",
        f"{pid}/register",
        json_body={
            "messaging_product": "whatsapp",
            "pin": pin_value,
        },
    )


def deregister_phone_number(*, phone_number_id: str, pin: str) -> dict:
    pid = phone_number_id.strip()
    pin_value = pin.strip()
    return _request(
        "POST",
        f"{pid}/deregister",
        json_body={
            "messaging_product": "whatsapp",
            "pin": pin_value,
        },
    )


def diagnose_access(*, waba_id: str | None = None, phone_number_id: str | None = None) -> dict:
    """Tests d'accès Graph API pour diagnostiquer token / permissions."""
    waba = (waba_id or getattr(settings, "WHATSAPP_BUSINESS_ACCOUNT_ID", None) or "").strip()
    phone_id = (
        phone_number_id or getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", None) or ""
    ).strip()
    token = _access_token()
    results: dict[str, Any] = {
        "token_prefix": f"{token[:8]}…{token[-4:]}" if len(token) > 16 else "(court)",
        "api_version": _api_version(),
        "waba_id": waba,
        "phone_number_id": phone_id,
        "checks": {},
    }

    def _probe(label: str, method: str, path: str) -> None:
        try:
            payload = _request(method, path)
            results["checks"][label] = {"ok": True, "data": payload}
        except WhatsAppApiError as exc:
            err = exc.payload.get("error", {}) if isinstance(exc.payload, dict) else {}
            results["checks"][label] = {
                "ok": False,
                "message": str(exc),
                "code": err.get("code"),
                "error_subcode": err.get("error_subcode"),
            }

    _probe("me", "GET", "me?fields=id,name")
    if waba:
        _probe("waba", "GET", f"{waba}?fields=id,name,account_review_status")
        _probe("waba_phone_numbers", "GET", f"{waba}/phone_numbers")
    if phone_id:
        _probe("phone_number", "GET", f"{phone_id}?fields=id,display_phone_number,verified_name")

    return results
