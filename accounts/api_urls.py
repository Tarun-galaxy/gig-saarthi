"""Accounts API URLs — OTP registration, verification, JWT auth, profile."""

from django.urls import path
from . import api_views

app_name = 'accounts_api'

urlpatterns = [
    # Registration (2-step with OTP)
    path('register/', api_views.RegisterView.as_view(), name='register'),
    path('register/verify/', api_views.RegisterVerifyView.as_view(), name='register_verify'),

    # OTP endpoints
    path('otp/request/', api_views.OTPRequestView.as_view(), name='otp_request'),
    path('otp/verify/', api_views.OTPVerifyView.as_view(), name='otp_verify'),

    # Login
    path('login/', api_views.LoginView.as_view(), name='login'),

    # User profile (authenticated)
    path('me/', api_views.CurrentUserView.as_view(), name='current_user'),
    path('profile/', api_views.UserProfileView.as_view(), name='user_profile'),
]
