"""Bookings URLs — Web views for booking features."""

from django.urls import path
from . import views

app_name = 'bookings'

urlpatterns = [
    path('', views.booking_list, name='list'),
    path('create/', views.booking_create, name='create'),
    path('<int:pk>/', views.booking_detail, name='detail'),
    path('<int:pk>/cancel/', views.booking_cancel, name='cancel'),
    path('<int:pk>/update-status/', views.booking_update_status, name='update_status'),
    path('accept/<int:booking_id>/', views.booking_accept, name='accept'),
    path('reject/<int:booking_id>/', views.booking_reject, name='reject'),
    path('<int:pk>/status/', views.booking_match_status, name='match_status'),
    path('<int:pk>/track/', views.booking_tracking, name='tracking'),
    path('<int:pk>/worker-location/', views.worker_location_api, name='worker_location'),
]
