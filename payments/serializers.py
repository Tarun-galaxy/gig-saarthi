"""Payments serializers for DRF API."""

from rest_framework import serializers
from .models import Invoice, WorkerPayout


class InvoiceSerializer(serializers.ModelSerializer):
    booking_id = serializers.IntegerField(source='booking.id', read_only=True)

    class Meta:
        model = Invoice
        fields = [
            'id', 'booking_id', 'amount', 'tax', 'platform_fee',
            'worker_payout', 'status', 'razorpay_order_id',
            'generated_at', 'paid_at'
        ]
        read_only_fields = [
            'amount', 'tax', 'platform_fee', 'worker_payout',
            'razorpay_order_id', 'generated_at'
        ]


class WorkerPayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkerPayout
        fields = [
            'id', 'worker', 'invoice', 'amount', 'status',
            'payout_date', 'transaction_reference'
        ]
