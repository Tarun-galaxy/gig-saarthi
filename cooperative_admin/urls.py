"""Cooperative Admin URLs — Web views for cooperative management."""

from django.urls import path
from . import views

app_name = 'cooperative_admin'

urlpatterns = [
    path('', views.admin_dashboard, name='dashboard'),
    path('bookings/', views.admin_booking_monitor, name='admin_booking_monitor'),
    path('api/stats/', views.admin_api_stats, name='admin_api_stats'),
    path('workers/', views.worker_verification_list, name='worker_verification'),
    path('workers/<int:worker_id>/verify/', views.verify_worker, name='verify_worker'),
    path('workers/<int:worker_id>/reject/', views.reject_worker, name='reject_worker'),
    path('cooperatives/', views.cooperative_list, name='cooperative_list'),
    path('cooperatives/<int:pk>/', views.cooperative_detail, name='cooperative_detail'),
    path('insurance/', views.insurance_management, name='insurance_management'),
    path('insurance/enroll/<int:worker_id>/', views.enroll_insurance, name='enroll_insurance'),
    path('insurance/approve/<int:policy_id>/', views.approve_insurance, name='approve_insurance'),
]

