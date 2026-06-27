"""Notifications SOS aux contacts de confiance (e-mail + alerte in-app)."""

from __future__ import annotations

import logging
import re

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

from users.models import User

from .models import SafetyAlert, TrustedContact, TrackingSession

logger = logging.getLogger(__name__)


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        return ""
    if digits.startswith("243"):
        return digits
    if digits.startswith("0") and len(digits) >= 9:
        return "243" + digits[1:]
    return digits


def find_user_by_phone(phone: str) -> User | None:
    normalized = normalize_phone(phone)
    if len(normalized) < 9:
        return None
    suffix = normalized[-9:]
    for user in User.objects.filter(phone_user__isnull=False).exclude(phone_user=""):
        if normalize_phone(user.phone_user).endswith(suffix):
            return user
    return None


def find_user_by_email(email: str) -> User | None:
    target = (email or "").strip().lower()
    if not target or "@" not in target:
        return None
    return User.objects.filter(email__iexact=target).first()


def find_ssu_user_for_contact(contact: TrustedContact) -> User | None:
    """Retrouve un compte SSU lié au contact (téléphone ou e-mail)."""
    by_phone = find_user_by_phone(contact.phone)
    if by_phone:
        return by_phone
    return find_user_by_email(contact.email)


def _tracking_url(token: str) -> str:
    base = (getattr(settings, "FRONTEND_URL", None) or "http://localhost").rstrip("/")
    return f"{base}/suivi/{token}"


def _send_tracking_email(
    *,
    to_email: str,
    contact_name: str,
    initiator_name: str,
    track_url: str,
    subject: str,
    template_name: str,
    extra_context: dict | None = None,
) -> bool:
    if not to_email:
        return False
    context = {
        "contact_name": contact_name,
        "initiator_name": initiator_name,
        "track_url": track_url,
        "support_email": getattr(settings, "SUPPORT_EMAIL", None),
        **(extra_context or {}),
    }
    html_content = render_to_string(template_name, context)
    text_content = (
        f"Bonjour {contact_name},\n\n"
        f"{initiator_name} — {subject}\n"
        f"Suivez en direct : {track_url}\n"
    )
    try:
        from users.email_utils import send_transactional_email

        send_transactional_email(
            subject=subject,
            plain_body=text_content,
            html_body=html_content,
            to=[to_email],
        )
        return True
    except Exception:
        logger.exception("Échec envoi e-mail à %s", to_email)
        return False


def _send_sos_email(*, to_email: str, contact_name: str, initiator_name: str, track_url: str) -> bool:
    return _send_tracking_email(
        to_email=to_email,
        contact_name=contact_name,
        initiator_name=initiator_name,
        track_url=track_url,
        subject=f"[SSU Bokengi] Alerte SOS de {initiator_name}",
        template_name="emails/sos_alert.html",
    )


def _notify_trusted_contacts(
    session: TrackingSession,
    contact_ids: list[int],
    *,
    kind: str,
    message: str,
    email_subject: str,
    email_template: str,
    email_extra: dict | None = None,
) -> dict:
    initiator = session.user
    initiator_name = initiator.username or initiator.email or "Un proche"
    track_url = _tracking_url(session.token)

    contacts = list(
        TrustedContact.objects.filter(user=initiator, id__in=contact_ids)
    )
    stats = {"in_app": 0, "email": 0, "skipped": 0}

    for contact in contacts:
        recipient_user = find_ssu_user_for_contact(contact)
        notified = False

        if recipient_user and recipient_user.id != initiator.id:
            _, created = SafetyAlert.objects.get_or_create(
                recipient=recipient_user,
                tracking_session=session,
                kind=kind,
                defaults={
                    "initiator": initiator,
                    "trusted_contact": contact,
                    "message": message,
                },
            )
            if created:
                stats["in_app"] += 1
            notified = True

            account_email = (recipient_user.email or "").strip()
            if account_email and _send_tracking_email(
                to_email=account_email,
                contact_name=contact.name,
                initiator_name=initiator_name,
                track_url=track_url,
                subject=email_subject,
                template_name=email_template,
                extra_context=email_extra,
            ):
                stats["email"] += 1
                notified = True

        contact_email = (contact.email or "").strip()
        if contact_email and (
            not recipient_user
            or contact_email.lower() != (recipient_user.email or "").strip().lower()
        ):
            if _send_tracking_email(
                to_email=contact_email,
                contact_name=contact.name,
                initiator_name=initiator_name,
                track_url=track_url,
                subject=email_subject,
                template_name=email_template,
                extra_context=email_extra,
            ):
                stats["email"] += 1
                notified = True

        if not notified:
            stats["skipped"] += 1

    session.last_shared_at = timezone.now()
    session.save(update_fields=["last_shared_at"])
    return stats


def notify_sos_contacts(
    session: TrackingSession,
    contact_ids: list[int],
) -> dict:
    """Notifie les contacts sélectionnés pour un SOS."""
    initiator_name = session.user.username or session.user.email or "Un proche"
    return _notify_trusted_contacts(
        session,
        contact_ids,
        kind="sos",
        message=f"{initiator_name} a déclenché un SOS.",
        email_subject=f"[SSU Bokengi] Alerte SOS de {initiator_name}",
        email_template="emails/sos_alert.html",
    )


def notify_trip_contacts(
    session: TrackingSession,
    contact_ids: list[int],
    *,
    dest_label: str = "",
) -> dict:
    """Notifie les contacts sélectionnés pour un trajet « Je rentre »."""
    initiator_name = session.user.username or session.user.email or "Un proche"
    dest_part = f" vers {dest_label}" if dest_label else ""
    return _notify_trusted_contacts(
        session,
        contact_ids,
        kind="trip",
        message=f"{initiator_name} partage son trajet{dest_part}.",
        email_subject=f"[SSU Bokengi] {initiator_name} partage son trajet",
        email_template="emails/trip_alert.html",
        email_extra={"dest_label": dest_label},
    )


def notify_checkin_contacts(
    session: TrackingSession,
    contact_ids: list[int],
    *,
    duration_minutes: int = 0,
) -> dict:
    """Notifie les contacts au démarrage d'un check-in sécurité."""
    initiator_name = session.user.username or session.user.email or "Un proche"
    duration_part = f" ({duration_minutes} min)" if duration_minutes else ""
    return _notify_trusted_contacts(
        session,
        contact_ids,
        kind="checkin",
        message=f"{initiator_name} a démarré un check-in sécurité{duration_part}.",
        email_subject=f"[SSU Bokengi] Check-in de {initiator_name}",
        email_template="emails/checkin_alert.html",
        email_extra={"duration_minutes": duration_minutes},
    )


def notify_checkin_missed_contacts(
    session: TrackingSession,
    contact_ids: list[int],
) -> dict:
    """Alerte les contacts lorsqu'un check-in n'est pas confirmé à temps."""
    initiator = session.user
    initiator_name = initiator.username or initiator.email or "Un proche"
    track_url = _tracking_url(session.token)
    message = f"{initiator_name} n'a pas confirmé son check-in à temps."

    contacts = list(
        TrustedContact.objects.filter(user=initiator, id__in=contact_ids)
    )
    stats = {"in_app": 0, "email": 0, "skipped": 0}

    for contact in contacts:
        recipient_user = find_ssu_user_for_contact(contact)
        notified = False

        if recipient_user and recipient_user.id != initiator.id:
            SafetyAlert.objects.create(
                recipient=recipient_user,
                initiator=initiator,
                trusted_contact=contact,
                tracking_session=session,
                kind="checkin",
                message=message,
            )
            stats["in_app"] += 1
            notified = True

            account_email = (recipient_user.email or "").strip()
            if account_email and _send_tracking_email(
                to_email=account_email,
                contact_name=contact.name,
                initiator_name=initiator_name,
                track_url=track_url,
                subject=f"[SSU Bokengi] Check-in manqué — {initiator_name}",
                template_name="emails/checkin_missed_alert.html",
            ):
                stats["email"] += 1
                notified = True

        contact_email = (contact.email or "").strip()
        if contact_email and (
            not recipient_user
            or contact_email.lower() != (recipient_user.email or "").strip().lower()
        ):
            if _send_tracking_email(
                to_email=contact_email,
                contact_name=contact.name,
                initiator_name=initiator_name,
                track_url=track_url,
                subject=f"[SSU Bokengi] Check-in manqué — {initiator_name}",
                template_name="emails/checkin_missed_alert.html",
            ):
                stats["email"] += 1
                notified = True

        if not notified:
            stats["skipped"] += 1

    session.last_shared_at = timezone.now()
    session.save(update_fields=["last_shared_at"])
    return stats
