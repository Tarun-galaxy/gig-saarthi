from django.conf import settings


def mapbox_token(request):
    """Make Mapbox access token available in all templates."""
    return {
        'mapbox_token': getattr(settings, 'MAPBOX_ACCESS_TOKEN', ''),
    }
