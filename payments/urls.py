"""Payments URLs — Razorpay checkout, webhooks, invoice management."""

from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Invoices
    path('', views.invoice_list, name='list'),
    path('invoice/<int:pk>/', views.invoice_detail, name='invoice_detail'),

    # Razorpay checkout flow
    path('pay/<int:booking_id>/', views.initiate_payment, name='initiate'),
    path('verify/', views.payment_verify, name='verify'),
    path('success/', views.payment_success, name='success'),
    path('failed/', views.payment_failed, name='failed'),

    # Webhook
    path('webhook/', views.payment_webhook, name='webhook'),

    # Demo payment (for testing without Razorpay keys)
    path('demo/<int:booking_id>/', views.demo_payment, name='demo'),
]
