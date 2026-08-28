"""Notifications API views for DRF."""

from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(generics.ListAPIView):
    """List notifications for the authenticated user."""

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def unread_count(request):
    """Get count of unread notifications."""
    count = Notification.objects.filter(
        user=request.user, is_read=False
    ).count()
    return Response({'unread_count': count})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def mark_read_api(request, pk):
    """Mark a notification as read."""
    try:
        notification = Notification.objects.get(pk=pk, user=request.user)
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response({'status': 'ok'})
    except Notification.DoesNotExist:
        return Response(
            {'error': 'Notification not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def mark_all_read_api(request):
    """Mark all notifications as read."""
    updated = Notification.objects.filter(
        user=request.user, is_read=False
    ).update(is_read=True)
    return Response({'marked_read': updated})
