"""Bookings API URLs."""

from django.urls import path
from . import api_views

app_name = 'bookings_api'

urlpatterns = [
    path('', api_views.BookingListView.as_view(), name='list'),
    path('create/', api_views.BookingCreateView.as_view(), name='create'),
    path('<int:pk>/', api_views.BookingDetailView.as_view(), name='detail'),
    path('categories/', api_views.ServiceCategoryListView.as_view(), name='categories'),
]
