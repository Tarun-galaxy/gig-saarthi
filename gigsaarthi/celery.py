"""
Celery configuration for Gig Saarthi.

Handles background tasks:
- Booking matching (async)
- Auto-reassignment on timeout
- Demand forecasting (Part 4)
- Notification sending
"""

import os
from celery import Celery

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gigsaarthi.settings.dev')

app = Celery('gigsaarthi')

# Read config from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task to verify Celery is working."""
    print(f'Request: {self.request!r}')


# Periodic task schedule (Celery Beat)
app.conf.beat_schedule = {
    'check-pending-accepts': {
        'task': 'bookings.tasks.check_pending_accepts',
        'schedule': 30.0,  # Run every 30 seconds
    },
    'daily-forecast': {
        'task': 'cooperative_admin.tasks.generate_daily_forecast',
        'schedule': 86400.0,  # Run once daily
    },
}
app.conf.timezone = 'Asia/Kolkata'
