"""Workers API URLs."""

from django.urls import path
from . import api_views

app_name = 'workers_api'

urlpatterns = [
    path('', api_views.WorkerListView.as_view(), name='list'),
    path('me/', api_views.MyWorkerProfileView.as_view(), name='my_profile'),
    path('<int:pk>/', api_views.WorkerDetailView.as_view(), name='detail'),
]
