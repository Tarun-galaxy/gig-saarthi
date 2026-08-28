"""Payments app — Invoice and payout models for Razorpay integration."""

from django.db import models
from core.models import TimeStampedModel


class Invoice(TimeStampedModel):
    """Invoice generated for completed bookings."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('refunded', 'Refunded'),
        ('failed', 'Failed'),
    ]

    booking = models.OneToOneField(
        'bookings.Booking',
        on_delete=models.CASCADE,
        related_name='invoice'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Total amount charged to customer (INR)"
    )
    tax = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="GST/tax amount (INR)"
    )
    platform_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Cooperative platform fee (INR)"
    )
    worker_payout = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Amount to be paid to the worker (INR)"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    # Razorpay fields
    razorpay_order_id = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Razorpay order ID"
    )
    razorpay_payment_id = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Razorpay payment ID (set after successful payment)"
    )
    razorpay_signature = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text="Razorpay payment signature for verification"
    )

    generated_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'
        ordering = ['-generated_at']

    def __str__(self):
        return f"Invoice #{self.pk}: ₹{self.amount} — {self.status}"

    def calculate_splits(self, platform_fee_percent=5):
        """
        Calculate platform fee and worker payout.
        Platform fee is a percentage of the total amount (5% cooperative fee).
        """
        from decimal import Decimal
        fee_rate = Decimal(str(platform_fee_percent)) / Decimal('100')
        gst_rate = Decimal('0.18')
        self.platform_fee = self.amount * fee_rate
        self.tax = self.amount * gst_rate
        self.worker_payout = self.amount - self.platform_fee
        return {
            'amount': self.amount,
            'tax': self.tax,
            'platform_fee': self.platform_fee,
            'worker_payout': self.worker_payout,
        }


class WorkerPayout(TimeStampedModel):
    """Record of payouts made to workers."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    worker = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='payouts'
    )
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='worker_payouts'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Amount paid to worker (INR)"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    payout_date = models.DateTimeField(blank=True, null=True)
    transaction_reference = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Bank/UPI transaction reference number"
    )

    class Meta:
        verbose_name = 'Worker Payout'
        verbose_name_plural = 'Worker Payouts'
        ordering = ['-created_at']

    def __str__(self):
        return f"Payout to {self.worker.get_full_name()}: ₹{self.amount} [{self.status}]"
