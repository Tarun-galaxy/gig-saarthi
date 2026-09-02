"""Workers URLs — Web views for worker features."""

from django.urls import path
from . import views

app_name = 'workers'

urlpatterns = [
    path('', views.worker_list, name='list'),
    path('dashboard/', views.worker_dashboard, name='dashboard'),
    path('onboarding/', views.worker_onboarding, name='onboarding'),
    path('<int:pk>/', views.worker_detail, name='detail'),
    path('me/', views.my_profile, name='my_profile'),
    path('earnings/', views.worker_earnings, name='earnings'),
    path('api/ai-chat/', views.worker_ai_chat_api, name='ai_chat_api'),
    path('api/location/', views.worker_update_location, name='update_location_api'),
]
