"""Notifications serializers for DRF API."""

from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_notification_type_display', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id', 'title', 'message', 'notification_type', 'type_display',
            'is_read', 'related_booking', 'created_at'
        ]
        read_only_fields = ['created_at']
