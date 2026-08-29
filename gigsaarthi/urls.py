"""Gig Saarthi URL Configuration."""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from core.views import health_check


urlpatterns = [
    # Django Admin
    path('admin/', admin.site.urls),

    # App URLs
    path('', include('core.urls')),
    path('accounts/', include('accounts.urls')),
    path('bookings/', include('bookings.urls')),
    path('workers/', include('workers.urls')),
    path('customers/', include('customers.urls')),
    path('payments/', include('payments.urls')),
    path('ratings/', include('ratings.urls')),
    path('notifications/', include('notifications.urls')),
    path('coop-admin/', include('cooperative_admin.urls')),

    # Health check for UptimeRobot / Render keep-alive
    path('health/', health_check, name='health_check'),
    path('healthz/', health_check, name='healthz_check'),

    # DRF API
    path('api/', include('core.api_urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Custom error pages
handler404 = 'core.views.custom_404'
handler500 = 'core.views.custom_500'
