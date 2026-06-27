import logging

from celery import shared_task

from .models import TrackingSession
from .notify import notify_sos_contacts

logger = logging.getLogger(__name__)


@shared_task(name="safety.tasks.notify_sos_contacts")
def notify_sos_contacts_task(session_id: int, contact_ids: list[int]):
    try:
        session = TrackingSession.objects.select_related("user").get(pk=session_id)
    except TrackingSession.DoesNotExist:
        logger.warning("notify_sos_contacts: session %s introuvable", session_id)
        return
    stats = notify_sos_contacts(session, contact_ids)
    logger.info("SOS session %s — notifications: %s", session_id, stats)
    return stats
