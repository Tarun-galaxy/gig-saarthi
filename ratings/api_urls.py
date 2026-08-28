"""Ratings API URLs."""

from django.urls import path
from . import api_views

app_name = 'ratings_api'

urlpatterns = [
    path('', api_views.ReviewListView.as_view(), name='list'),
    path('create/', api_views.ReviewCreateView.as_view(), name='create'),
    path('worker/<int:worker_id>/', api_views.WorkerReviewsView.as_view(), name='worker_reviews'),
]
