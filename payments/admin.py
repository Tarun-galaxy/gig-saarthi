"""Payments admin — Register payment-related models."""

from django.contrib import admin
from .models import Invoice, WorkerPayout


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'booking', 'amount', 'tax', 'platform_fee',
        'worker_payout', 'status', 'generated_at', 'paid_at'
    )
    list_filter = ('status',)
    search_fields = (
        'booking__id', 'razorpay_order_id',
        'razorpay_payment_id'
    )
    readonly_fields = ('generated_at',)


@admin.register(WorkerPayout)
class WorkerPayoutAdmin(admin.ModelAdmin):
    list_display = (
        'worker', 'invoice', 'amount', 'status',
        'payout_date', 'transaction_reference'
    )
    list_filter = ('status',)
    search_fields = (
        'worker__username', 'transaction_reference'
    )
