"""Notifications API URLs."""

from django.urls import path
from . import api_views

app_name = 'notifications_api'

urlpatterns = [
    path('', api_views.NotificationListView.as_view(), name='list'),
    path('unread-count/', api_views.unread_count, name='unread_count'),
    path('<int:pk>/read/', api_views.mark_read_api, name='mark_read'),
    path('mark-all-read/', api_views.mark_all_read_api, name='mark_all_read'),
]
