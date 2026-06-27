"""Envoi d'e-mails transactionnels avec en-têtes anti-spam."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.mail import EmailMultiAlternatives


def resolve_from_email() -> str:
    configured = (getattr(settings, "DEFAULT_FROM_EMAIL", None) or "").strip()
    if configured:
        return configured
    user = (getattr(settings, "EMAIL_HOST_USER", None) or "").strip()
    app = getattr(settings, "APP_NAME", "SSU Bokengi")
    return f"{app} <{user}>" if user else app


def resolve_reply_to() -> str | None:
    support = (getattr(settings, "SUPPORT_EMAIL", None) or "").strip()
    if support:
        return support
    user = (getattr(settings, "EMAIL_HOST_USER", None) or "").strip()
    return user or None


def send_transactional_email(
    *,
    subject: str,
    plain_body: str,
    html_body: str | None,
    to: list[str],
    reply_to: str | None = None,
) -> None:
    """Envoie un e-mail HTML + texte avec en-têtes favorisant la boîte de réception."""
    recipients = [addr.strip() for addr in to if addr and addr.strip()]
    if not recipients:
        return

    clean_subject = subject.strip()
    if clean_subject.startswith("[Django]"):
        clean_subject = clean_subject.replace("[Django]", "", 1).strip()

    message = EmailMultiAlternatives(
        subject=clean_subject,
        body=plain_body.strip(),
        from_email=resolve_from_email(),
        to=recipients,
    )
    if html_body:
        message.attach_alternative(html_body, "text/html")

    reply = reply_to or resolve_reply_to()
    headers: dict[str, str] = {
        "Auto-Submitted": "auto-generated",
        "X-Auto-Response-Suppress": "All",
        "X-Entity-Ref-ID": str(uuid.uuid4()),
    }
    if reply:
        message.reply_to = [reply]
        headers["Reply-To"] = reply
    message.extra_headers = headers
    message.send(fail_silently=False)
