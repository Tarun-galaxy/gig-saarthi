"""Core API URLs — DRF endpoints for all apps."""

from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

app_name = 'api'

urlpatterns = [
    # JWT Auth
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Auth endpoints
    path('auth/', include('accounts.api_urls')),

    # App APIs
    path('workers/', include('workers.api_urls')),
    path('customers/', include('customers.api_urls')),
    path('bookings/', include('bookings.api_urls')),
    path('payments/', include('payments.api_urls')),
    path('ratings/', include('ratings.api_urls')),
    path('notifications/', include('notifications.api_urls')),
]
