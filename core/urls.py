"""Core URLs — Homepage and shared views."""

from django.urls import path
from . import views, api_views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('set-language/', views.set_language, name='set_language'),

    # Geoapify API endpoints
    path('api/autocomplete/', api_views.api_autocomplete, name='api_autocomplete'),
    path('api/geocode/', api_views.api_geocode, name='api_geocode'),
    path('api/reverse-geocode/', api_views.api_reverse_geocode, name='api_reverse_geocode'),
    path('api/route/', api_views.api_route, name='api_route'),
    path('api/map-config/', api_views.api_map_config, name='api_map_config'),
]
