from celery import shared_task
from .models import UserActivityLog

@shared_task
def purge_activity_logs():
    UserActivityLog.purge_old_records(days=90)