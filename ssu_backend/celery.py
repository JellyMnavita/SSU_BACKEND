import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ssu_backend.settings')

app = Celery('ssu_backend')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()