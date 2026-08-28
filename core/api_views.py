"""Core API views — geocoding, autocomplete, routing."""

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .services.geoapify import (
    autocomplete_address,
    geocode_address,
    reverse_geocode,
    get_route,
    get_tile_url,
)


@login_required
def api_autocomplete(request):
    """
    GET /api/autocomplete/?q=...&bias=lat,lon

    Returns address suggestions for search-as-you-type.
    """
    query = request.GET.get("q", "").strip()
    bias = request.GET.get("bias", None)
    limit = min(int(request.GET.get("limit", 5)), 10)

    if not query:
        return JsonResponse({"results": []})

    results = autocomplete_address(query, bias=bias, limit=limit)
    return JsonResponse({"results": results})


@login_required
def api_geocode(request):
    """
    GET /api/geocode/?address=...

    Geocode a full address string.
    """
    address = request.GET.get("address", "").strip()
    if not address:
        return JsonResponse({"error": "address parameter required"}, status=400)

    result = geocode_address(address)
    if result is None:
        return JsonResponse({"error": "No results found"}, status=404)

    return JsonResponse(result)


@login_required
def api_reverse_geocode(request):
    """
    GET /api/reverse-geocode/?lat=...&lon=...

    Reverse geocode coordinates to a readable address.
    """
    try:
        lat = float(request.GET.get("lat", 0))
        lon = float(request.GET.get("lon", 0))
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid lat/lon"}, status=400)

    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return JsonResponse({"error": "Coordinates out of range"}, status=400)

    result = reverse_geocode(lat, lon)
    if result is None:
        return JsonResponse({"error": "No address found"}, status=404)

    return JsonResponse(result)


@login_required
def api_route(request):
    """
    GET /api/route/?origin_lat=...&origin_lon=...&dest_lat=...&dest_lon=...&mode=drive

    Get route between two points.
    """
    try:
        origin_lat = float(request.GET.get("origin_lat", 0))
        origin_lon = float(request.GET.get("origin_lon", 0))
        dest_lat = float(request.GET.get("dest_lat", 0))
        dest_lon = float(request.GET.get("dest_lon", 0))
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid coordinates"}, status=400)

    mode = request.GET.get("mode", "drive")
    result = get_route(origin_lat, origin_lon, dest_lat, dest_lon, mode)
    return JsonResponse(result)


@login_required
def api_map_config(request):
    """
    GET /api/map-config/

    Returns map tile URL, attribution, and API key for client-side Leaflet init.
    """
    tile = get_tile_url()
    return JsonResponse({
        "tile_url": tile["url"],
        "attribution": tile["attribution"],
        "is_geoapify": tile["is_geoapify"],
    })
