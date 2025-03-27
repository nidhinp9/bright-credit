from __future__ import absolute_import
import os
from celery import Celery
from celery.schedules import crontab  # ✅ for scheduled tasks

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bright_credit.settings')

app = Celery('bright_credit')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# ✅ Schedule task to run daily at 12 AM IST
app.conf.beat_schedule = {
    'run-billing-daily': {
        'task': 'loan.tasks.run_billing',
        'schedule': crontab(hour=0, minute=0),  # ✅ Removed timezone
    },
}
