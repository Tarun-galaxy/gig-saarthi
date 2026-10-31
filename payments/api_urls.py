"""Payments API URLs."""

from django.urls import path
from . import api_views, views

app_name = 'payments_api'

urlpatterns = [
    path('invoices/', api_views.InvoiceListView.as_view(), name='invoice_list'),
    path('invoices/<int:pk>/', api_views.InvoiceDetailView.as_view(), name='invoice_detail'),
    # Same signed, idempotent handler as the web route (payments/urls.py)
    path('webhook/', views.payment_webhook, name='webhook'),
]
