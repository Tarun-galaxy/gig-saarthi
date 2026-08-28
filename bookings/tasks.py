"""
Celery tasks for bookings — async matching and auto-reassignment.

These tasks run in the background via Celery + Redis.
If Celery is not available, the matching runs synchronously in the signal handler.
"""

import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def match_booking(self, booking_id):
    """
    Async task to match a booking with the best available worker.
    
    Runs with a short delay after booking creation to allow
    the database transaction to commit fully.
    """
    from bookings.models import Booking
    from core.services.matching import find_and_assign_worker

    try:
        booking = Booking.objects.get(pk=booking_id)

        if booking.status != 'pending':
            logger.info(f"Booking #{booking_id} already {booking.status} — skipping match")
            return {'status': 'skipped', 'reason': f'Already {booking.status}'}

        result = find_and_assign_worker(booking)
        logger.info(f"Booking #{booking_id} matching result: {result}")
        return result

    except Booking.DoesNotExist:
        logger.error(f"Booking #{booking_id} not found")
        return {'status': 'error', 'reason': 'Booking not found'}

    except Exception as exc:
        logger.error(f"Booking #{booking_id} matching failed: {exc}")
        self.retry(countdown=30, exc=exc)


@shared_task(bind=True, max_retries=2)
def auto_reassign_booking(self, booking_id, exclude_worker_ids=None):
    """
    Async task to reassign a booking to the next available worker
    when the current worker rejects or times out.
    """
    from bookings.models import Booking
    from core.services.matching import reassign_to_next_worker

    try:
        booking = Booking.objects.get(pk=booking_id)

        if booking.status != 'matched':
            logger.info(f"Booking #{booking_id} not in 'matched' state — skipping reassignment")
            return {'status': 'skipped'}

        if exclude_worker_ids is None:
            exclude_worker_ids = []

        # Add current worker to exclusion list
        if booking.worker_id:
            exclude_worker_ids.append(booking.worker_id)

        result = reassign_to_next_worker(booking, set(exclude_worker_ids))
        logger.info(f"Booking #{booking_id} reassignment result: {result}")
        return result

    except Booking.DoesNotExist:
        logger.error(f"Booking #{booking_id} not found")
        return {'status': 'error', 'reason': 'Booking not found'}

    except Exception as exc:
        logger.error(f"Booking #{booking_id} reassignment failed: {exc}")
        self.retry(countdown=30, exc=exc)


@shared_task
def check_pending_accepts():
    """
    Periodic task to check for matched bookings that have exceeded
    the accept timeout window. Auto-reassigns to next worker.
    
    Run every 30 seconds via Celery Beat:
    ('check-pending-accepts', {'task': 'bookings.tasks.check_pending_accepts', 'schedule': 30.0})
    """
    from bookings.models import Booking
    from core.services.matching import get_accept_timeout

    now = timezone.now()
    timed_out = []

    # Find matched bookings where the worker hasn't accepted within timeout
    matched_bookings = Booking.objects.filter(
        status='matched',
        matched_at__isnull=False,
        worker__isnull=False,
    )

    for booking in matched_bookings:
        timeout = get_accept_timeout(booking)
        deadline = booking.matched_at + timezone.timedelta(seconds=timeout)

        if now > deadline:
            # Worker timed out — reassign
            logger.info(f"Booking #{booking.pk}: Worker accept timeout — reassigning")
            auto_reassign_booking.delay(booking.pk)
            timed_out.append(booking.pk)

    if timed_out:
        logger.info(f"Auto-reassigned {len(timed_out)} timed-out bookings: {timed_out}")

    return {'timed_out_count': len(timed_out), 'booking_ids': timed_out}
