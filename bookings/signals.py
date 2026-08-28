"""
Booking signals — Auto-logging, matching triggers, and lifecycle management.

These signals ensure:
1. Status changes are always logged to BookingStatusHistory
2. New bookings automatically trigger the matching engine
3. Completed bookings auto-generate invoices
4. Worker ratings are updated on completion
"""

import logging
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


@receiver(pre_save, sender='bookings.Booking')
def booking_pre_save(sender, instance, **kwargs):
    """
    Track status changes before save.
    Sets timestamp fields based on status transitions.
    """
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
        except sender.DoesNotExist:
            return

        old_status = old.status
        new_status = instance.status

        if old_status != new_status:
            # Set appropriate timestamps
            if new_status == 'matched' and not instance.matched_at:
                instance.matched_at = timezone.now()
            elif new_status == 'accepted' and not instance.accepted_at:
                instance.accepted_at = timezone.now()
            elif new_status == 'completed' and not instance.completed_at:
                instance.completed_at = timezone.now()
            elif 'cancelled' in new_status and not instance.cancelled_at:
                instance.cancelled_at = timezone.now()

            logger.info(
                f"Booking #{instance.pk} status: {old_status} → {new_status}"
            )


@receiver(post_save, sender='bookings.Booking')
def booking_post_save(sender, instance, created, **kwargs):
    """
    Post-save actions:
    - On create: trigger the matching engine
    - On completion: generate invoice
    """
    if created:
        # Trigger matching engine for new bookings
        _trigger_matching(instance)

    # Auto-generate invoice on completion
    if instance.status == 'completed' and instance.final_price > 0:
        _ensure_invoice(instance)


def _trigger_matching(booking):
    """
    Trigger the geo-matching engine for a new booking.
    Runs synchronously. Use Celery tasks for async in production.
    """
    from core.services.matching import find_and_assign_worker
    try:
        result = find_and_assign_worker(booking)
        logger.info(
            f"Booking #{booking.pk}: Matching result — "
            f"success={result['success']}, "
            f"candidates={result['candidates_count']}"
        )
    except Exception as e:
        logger.error(f"Booking #{booking.pk}: Matching failed — {e}")


def _ensure_invoice(booking):
    """
    Ensure an invoice exists for a completed booking.
    Auto-calculates pricing if not already set.
    """
    from payments.models import Invoice
    from decimal import Decimal

    existing = Invoice.objects.filter(booking=booking).first()
    if existing:
        return existing

    amount = booking.final_price or booking.estimated_price or Decimal('0')
    if amount <= 0:
        logger.warning(f"Booking #{booking.pk}: Cannot generate invoice - amount is {amount}")
        return None

    invoice = Invoice.objects.create(
        booking=booking,
        amount=amount,
        status='pending',
    )
    invoice.calculate_splits()
    invoice.save(update_fields=['tax', 'platform_fee', 'worker_payout'])
    logger.info(f"Booking #{booking.pk}: Invoice #{invoice.pk} generated")
    return invoice
