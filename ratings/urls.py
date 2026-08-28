"""Ratings URLs — Web views for review features."""

from django.urls import path
from . import views

app_name = 'ratings'

urlpatterns = [
    path('submit/<int:booking_id>/', views.submit_review, name='submit'),
]
