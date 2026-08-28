"""Bookings serializers for DRF API."""

from rest_framework import serializers
from .models import ServiceCategory, Booking, BookingStatusHistory


class ServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCategory
        fields = ['id', 'name', 'icon', 'description', 'base_price']


class BookingStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = BookingStatusHistory
        fields = ['id', 'status', 'changed_by', 'changed_by_name', 'notes', 'created_at']

    def get_changed_by_name(self, obj):
        if obj.changed_by:
            return obj.changed_by.get_full_name() or obj.changed_by.username
        return 'System'


class BookingSerializer(serializers.ModelSerializer):
    """Full booking serializer."""

    customer_name = serializers.SerializerMethodField()
    worker_name = serializers.SerializerMethodField()
    service_category_name = serializers.CharField(
        source='service_category.name', read_only=True
    )
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    status_history = BookingStatusHistorySerializer(many=True, read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'customer', 'customer_name', 'worker', 'worker_name',
            'service_category', 'service_category_name',
            'description', 'scheduled_datetime', 'is_emergency', 'status',
            'status_display', 'address_text', 'latitude', 'longitude',
            'estimated_price', 'final_price',
            'created_at', 'matched_at', 'accepted_at', 'completed_at',
            'cancelled_at', 'status_history'
        ]
        read_only_fields = [
            'customer', 'status', 'created_at', 'matched_at',
            'accepted_at', 'completed_at', 'cancelled_at'
        ]

    def get_customer_name(self, obj):
        return obj.customer.get_full_name() or obj.customer.username

    def get_worker_name(self, obj):
        if obj.worker:
            return obj.worker.get_full_name() or obj.worker.username
        return None


class BookingCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new bookings."""

    class Meta:
        model = Booking
        fields = [
            'service_category', 'description', 'scheduled_datetime',
            'is_emergency', 'address_text', 'latitude', 'longitude'
        ]

    def create(self, validated_data):
        validated_data['customer'] = self.context['request'].user
        validated_data['status'] = 'pending'
        return super().create(validated_data)
