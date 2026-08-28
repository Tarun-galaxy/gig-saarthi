"""Bookings app — Service categories, bookings, and status history."""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import TimeStampedModel


class ServiceCategory(TimeStampedModel):
    """Categories of services offered on the platform."""

    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text="Icon class name or emoji"
    )
    description = models.TextField(blank=True, default='')
    base_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Base/starting price for this service category (INR)"
    )
    is_active = models.BooleanField(default=True)
    related_skills = models.ManyToManyField(
        'workers.Skill',
        blank=True,
        related_name='service_categories',
        help_text="Skills required for this service category"
    )

    class Meta:
        verbose_name = 'Service Category'
        verbose_name_plural = 'Service Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Booking(TimeStampedModel):
    """
    Core booking model — represents a service request from a customer.
    Lifecycle: pending → matched → accepted → in_progress → completed
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('matched', 'Matched'),
        ('accepted', 'Accepted'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled_by_customer', 'Cancelled by Customer'),
        ('cancelled_by_worker', 'Cancelled by Worker'),
        ('disputed', 'Disputed'),
    ]

    customer = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='customer_bookings',
        help_text="Customer who made the booking"
    )
    worker = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='worker_bookings',
        help_text="Worker assigned to this booking (set after matching)"
    )
    service_category = models.ForeignKey(
        ServiceCategory,
        on_delete=models.CASCADE,
        related_name='bookings',
        help_text="Type of service requested"
    )
    description = models.TextField(
        help_text="Customer's description of the service needed"
    )
    scheduled_datetime = models.DateTimeField(
        help_text="When the customer wants the service"
    )
    is_emergency = models.BooleanField(
        default=False,
        help_text="Emergency bookings auto-match to nearest worker ASAP"
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='pending'
    )

    # Location
    address_text = models.TextField(
        blank=True,
        default='',
        help_text="Text address for the service location"
    )
    latitude = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(-90), MaxValueValidator(90)]
    )
    longitude = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(-180), MaxValueValidator(180)]
    )

    # Pricing
    estimated_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Estimated price shown to customer (INR)"
    )
    final_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Final price after service completion (INR)"
    )

    # Timestamps
    matched_at = models.DateTimeField(blank=True, null=True)
    accepted_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)

    # Cancellation reason
    cancellation_reason = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Booking'
        verbose_name_plural = 'Bookings'
        ordering = ['-created_at']

    def __str__(self):
        worker_name = self.worker.get_full_name() if self.worker else 'Unassigned'
        return (
            f"Booking #{self.pk}: {self.service_category.name} — "
            f"{self.customer.get_full_name()} → {worker_name} [{self.status}]"
        )

    @property
    def can_be_cancelled(self):
        """Check if booking can still be cancelled."""
        return self.status in ('pending', 'matched', 'accepted')

    @property
    def duration_estimate_hours(self):
        """Estimated hours for the service (could be refined per category)."""
        return 2  # Default estimate, can be made dynamic


class BookingStatusHistory(TimeStampedModel):
    """Audit trail for all status changes on a booking."""

    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name='status_history'
    )
    status = models.CharField(max_length=30, choices=Booking.STATUS_CHOICES)
    changed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who triggered the status change"
    )
    notes = models.TextField(
        blank=True,
        default='',
        help_text="Optional notes about the status change"
    )

    class Meta:
        verbose_name = 'Booking Status History'
        verbose_name_plural = 'Booking Status Histories'
        ordering = ['-created_at']

    def __str__(self):
        return f"Booking #{self.booking.pk}: {self.status} at {self.created_at}"
