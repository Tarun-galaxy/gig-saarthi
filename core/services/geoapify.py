"""
Geoapify integration — tiles, geocoding, autocomplete, routing.

Free tier: 3,000 requests/day (https://geoapify.com/pricing)
Docs: https://docs.geoapify.com/

Set GEOAPIFY_API_KEY in your .env file.
Get a free key at: https://myprojects.geoapify.com/
"""

import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GEOAPIFY_BASE_URL = "https://api.geoapify.com/v1"
GEOAPIFY_MAPS_URL = "https://maps.geoapify.com/v1"


def _get_api_key():
    return getattr(settings, "GEOAPIFY_API_KEY", "")


def get_tile_url(style="osm-bright"):
    """Return the Geoapify tile URL template for use in Leaflet."""
    api_key = _get_api_key()
    if not api_key:
        # Fallback to free OpenStreetMap tiles
        return {
            "url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            "attribution": "&copy; OpenStreetMap contributors",
            "is_geoapify": False,
        }
    return {
        "url": (
            f"https://maps.geoapify.com/v1/tile/{style}/"
            "{{z}}/{{x}}/{{y}}.png?apiKey={key}"
        ).format(key=api_key),
        "attribution": (
            'Powered by <a href="https://geoapify.com/">Geoapify</a> | '
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        ),
        "is_geoapify": True,
    }


# ──────────────────────────────────────────────
#  Autocomplete
# ──────────────────────────────────────────────

def autocomplete_address(query, bias=None, limit=5):
    """
    Address autocomplete — returns suggestions as the user types.

    Args:
        query: Partial address string.
        bias: Optional "lat,lon" to bias results toward a location.
        limit: Max results (default 5).

    Returns:
        list of dicts: [{ lat, lon, formatted_address, city, postcode }, ...]
    """
    api_key = _get_api_key()
    if not api_key or not query.strip():
        return []

    url = f"{GEOAPIFY_BASE_URL}/geocode/autocomplete"
    params = {
        "text": query,
        "apiKey": api_key,
        "limit": limit,
    }
    if bias:
        params["bias"] = f"proximity:{bias}"

    try:
        resp = requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for f in data.get("features", []):
            props = f["properties"]
            coords = f["geometry"]["coordinates"]
            results.append({
                "lat": coords[1],
                "lon": coords[0],
                "formatted_address": props.get("formatted", ""),
                "city": props.get("city", ""),
                "state": props.get("state", ""),
                "postcode": props.get("postcode", ""),
                "country": props.get("country", ""),
            })
        return results

    except requests.RequestException as e:
        logger.error("Geoapify autocomplete failed: %s", e)
        return []


# ──────────────────────────────────────────────
#  Geocoding
# ──────────────────────────────────────────────

def geocode_address(address_text):
    """Geocode a full address string to coordinates."""
    api_key = _get_api_key()
    if not api_key:
        return None

    url = f"{GEOAPIFY_BASE_URL}/geocode/search"
    params = {
        "text": address_text,
        "apiKey": api_key,
        "limit": 1,
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        if not features:
            return None

        f = features[0]
        props = f["properties"]
        coords = f["geometry"]["coordinates"]
        return {
            "lat": coords[1],
            "lon": coords[0],
            "formatted_address": props.get("formatted", address_text),
            "city": props.get("city", ""),
            "state": props.get("state", ""),
        }

    except requests.RequestException as e:
        logger.error("Geoapify geocoding failed: %s", e)
        return None


def reverse_geocode(lat, lon):
    """Reverse geocode coordinates to a readable address."""
    api_key = _get_api_key()
    if not api_key:
        return None

    url = f"{GEOAPIFY_BASE_URL}/geocode/reverse"
    params = {"lat": lat, "lon": lon, "apiKey": api_key}

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        if not features:
            return None

        props = features[0]["properties"]
        return {
            "formatted_address": props.get("formatted", ""),
            "city": props.get("city", ""),
            "state": props.get("state", ""),
            "country": props.get("country", ""),
            "postcode": props.get("postcode", ""),
        }

    except requests.RequestException as e:
        logger.error("Geoapify reverse geocoding failed: %s", e)
        return None


# ──────────────────────────────────────────────
#  Routing
# ──────────────────────────────────────────────

def get_route(origin_lat, origin_lon, dest_lat, dest_lon, mode="drive"):
    """
    Get a route between two points using Geoapify Routing API.

    Args:
        origin_lat, origin_lon: Starting coordinates.
        dest_lat, dest_lon: Destination coordinates.
        mode: 'drive', 'walk', 'bicycle', 'motorcycle', 'scooter'.

    Returns:
        dict: { distance_km, duration_min, polyline, steps, geometry } or fallback.
    """
    api_key = _get_api_key()
    if not api_key:
        return _straight_line_fallback(origin_lat, origin_lon, dest_lat, dest_lon)

    url = f"{GEOAPIFY_BASE_URL}/routing"
    params = {
        "waypoints": f"{origin_lat},{origin_lon}|{dest_lat},{dest_lon}",
        "mode": mode,
        "apiKey": api_key,
        "details": "route_instructions,route_details",
        "lang": "en",
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("features"):
            return _straight_line_fallback(origin_lat, origin_lon, dest_lat, dest_lon)

        feature = data["features"][0]
        props = feature["properties"]
        geometry = feature.get("geometry", {})

        distance_m = props.get("distance", 0)
        duration_s = props.get("time", 0)

        # Extract polyline — GeoJSON is [lon, lat], convert to [lat, lon] for Leaflet
        polyline = []
        if geometry.get("coordinates"):
            coords = geometry["coordinates"]
            if geometry.get("type") == "LineString":
                polyline = [[c[1], c[0]] for c in coords]
            elif geometry.get("type") == "MultiLineString":
                for line in coords:
                    polyline.extend([[c[1], c[0]] for c in line])

        # Turn-by-turn instructions
        steps = []
        for leg in props.get("legs", []):
            for step in leg.get("steps", []):
                inst = step.get("instruction", {})
                text = inst.get("text", "") if isinstance(inst, dict) else str(inst)
                dist_m = step.get("distance", 0)
                steps.append({
                    "instruction": text,
                    "distance": f"{round(dist_m)}m" if dist_m >= 1000 else f"{round(dist_m)}m",
                    "time_s": step.get("time", 0),
                })

        return {
            "distance_km": round(distance_m / 1000, 1),
            "duration_min": round(duration_s / 60, 1),
            "polyline": polyline,
            "steps": steps,
            "geometry": geometry,
            "is_fallback": False,
        }

    except requests.RequestException as e:
        logger.error("Geoapify routing failed: %s", e)
        return _straight_line_fallback(origin_lat, origin_lon, dest_lat, dest_lon)


# ──────────────────────────────────────────────
#  Fallback
# ──────────────────────────────────────────────

def _straight_line_fallback(origin_lat, origin_lon, dest_lat, dest_lon):
    """Haversine fallback when Geoapify is unavailable."""
    import math

    R = 6371
    dlat = math.radians(dest_lat - origin_lat)
    dlon = math.radians(dest_lon - origin_lon)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(origin_lat)) * math.cos(math.radians(dest_lat)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance_km = R * c
    duration_min = round((distance_km / 30) * 60, 1)

    return {
        "distance_km": round(distance_km, 1),
        "duration_min": duration_min,
        "polyline": [[origin_lat, origin_lon], [dest_lat, dest_lon]],
        "steps": [],
        "geometry": {
            "type": "LineString",
            "coordinates": [[origin_lon, origin_lat], [dest_lon, dest_lat]],
        },
        "is_fallback": True,
    }
