"""Notifications app — In-app notification model."""

from django.db import models
from core.models import TimeStampedModel


class Notification(TimeStampedModel):
    """In-app notification for users."""

    TYPE_CHOICES = [
        ('booking_request', 'New Booking Request'),
        ('booking_accepted', 'Booking Accepted'),
        ('booking_completed', 'Booking Completed'),
        ('booking_cancelled', 'Booking Cancelled'),
        ('payment_received', 'Payment Received'),
        ('payment_failed', 'Payment Failed'),
        ('review_received', 'New Review'),
        ('verification_approved', 'Verification Approved'),
        ('verification_rejected', 'Verification Rejected'),
        ('insurance_update', 'Insurance Update'),
        ('system', 'System Notification'),
    ]

    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=30,
        choices=TYPE_CHOICES,
        default='system'
    )
    is_read = models.BooleanField(default=False)

    # Optional link to related object
    related_booking = models.ForeignKey(
        'bookings.Booking',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )

    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']

    def __str__(self):
        status = "✓" if self.is_read else "●"
        return f"{status} {self.title} → {self.user.get_full_name()}"

    @property
    def mark_as_read(self):
        self.is_read = True
        self.save(update_fields=['is_read'])
