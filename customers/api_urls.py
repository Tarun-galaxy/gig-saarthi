"""Customers API URLs."""

from django.urls import path
from . import api_views

app_name = 'customers_api'

urlpatterns = [
    path('me/', api_views.MyCustomerProfileView.as_view(), name='my_profile'),
]
