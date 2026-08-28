"""Ratings serializers for DRF API."""

from rest_framework import serializers
from .models import Review
from accounts.serializers import UserMinimalSerializer


class ReviewSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    worker_name = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            'id', 'booking', 'customer', 'customer_name',
            'worker', 'worker_name',
            'overall_rating', 'punctuality_rating', 'quality_rating',
            'comment', 'is_flagged', 'created_at'
        ]
        read_only_fields = ['customer', 'is_flagged', 'created_at']

    def get_customer_name(self, obj):
        return obj.customer.get_full_name() or obj.customer.username

    def get_worker_name(self, obj):
        return obj.worker.get_full_name() or obj.worker.username


class ReviewCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = [
            'booking', 'overall_rating', 'punctuality_rating',
            'quality_rating', 'comment'
        ]

    def create(self, validated_data):
        validated_data['customer'] = self.context['request'].user
        validated_data['worker'] = validated_data['booking'].worker
        return super().create(validated_data)
