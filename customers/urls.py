"""Customers URLs — Web views for customer features."""

from django.urls import path
from . import views

app_name = 'customers'

urlpatterns = [
    path('dashboard/', views.customer_dashboard, name='dashboard'),
    path('profile/', views.customer_profile, name='profile'),
    path('onboarding/', views.customer_onboarding, name='onboarding'),
    path('locations/', views.saved_locations, name='saved_locations'),
]
