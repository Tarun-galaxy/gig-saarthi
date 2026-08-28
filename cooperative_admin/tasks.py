"""
Celery tasks for cooperative admin — demand forecasting.
Runs daily via Celery Beat to generate predictions.
"""

import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def generate_daily_forecast():
    """
    Daily task to generate demand forecasts for all service categories.
    
    Runs via Celery Beat:
    ('daily-forecast', {'task': 'cooperative_admin.tasks.generate_daily_forecast', 'schedule': 86400.0})
    """
    from core.services.forecasting import generate_all_forecasts, save_forecasts

    try:
        logger.info("Starting daily demand forecast generation...")

        forecasts = generate_all_forecasts(region='Delhi NCR', days=7)
        saved = save_forecasts(forecasts)

        # Count shortages
        shortages = sum(1 for f in forecasts if f['is_shortage'])

        result = {
            'forecasts_generated': len(forecasts),
            'forecasts_saved': saved,
            'shortages_detected': shortages,
            'generated_at': timezone.now().isoformat(),
        }

        logger.info(
            f"Daily forecast complete: {saved} forecasts, "
            f"{shortages} shortages detected"
        )
        return result

    except Exception as e:
        logger.error(f"Daily forecast generation failed: {e}")
        raise


@shared_task
def generate_synthetic_data(weeks=12):
    """
    One-time task to generate synthetic historical booking data.
    Run manually: celery -A gigsaarthi call cooperative_admin.tasks.generate_synthetic_data
    """
    from core.services.forecasting import generate_synthetic_booking_data

    try:
        count = generate_synthetic_booking_data(region='Delhi NCR', weeks=weeks)
        logger.info(f"Generated {count} synthetic bookings")
        return {'bookings_created': count}
    except Exception as e:
        logger.error(f"Synthetic data generation failed: {e}")
        raise
