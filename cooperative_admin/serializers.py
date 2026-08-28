"""Cooperative Admin serializers for DRF API."""

from rest_framework import serializers
from .models import Cooperative


class CooperativeSerializer(serializers.ModelSerializer):
    worker_count = serializers.SerializerMethodField()

    class Meta:
        model = Cooperative
        fields = [
            'id', 'name', 'registration_number', 'region',
            'district', 'state', 'federation_level',
            'contact_person', 'contact_phone', 'established_date',
            'is_active', 'worker_count'
        ]

    def get_worker_count(self, obj):
        return obj.worker_count if hasattr(obj, 'worker_count') else obj.workers.count()
