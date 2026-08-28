"""Customers serializers for DRF API."""

from rest_framework import serializers
from .models import CustomerProfile, SavedLocation


class SavedLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedLocation
        fields = ['id', 'label', 'address', 'latitude', 'longitude', 'is_default']


class CustomerProfileSerializer(serializers.ModelSerializer):
    saved_locations = SavedLocationSerializer(many=True, read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = CustomerProfile
        fields = [
            'id', 'full_name', 'default_address',
            'default_latitude', 'default_longitude',
            'saved_locations', 'created_at'
        ]

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
