"""Core app — shared utilities, base models, and helpers for Gig Saarthi."""

from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base model with created/updated timestamps."""
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    class Meta:
        abstract = True
        ordering = ['-created_at']


class LocationMixin:
    """Mixin for location-based distance calculations using Haversine formula."""

    @staticmethod
    def haversine(lat1, lon1, lat2, lon2):
        """
        Calculate the great-circle distance (in km) between two points
        on Earth using the Haversine formula.
        """
        import math
        R = 6371  # Earth's radius in kilometers

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        a = (math.sin(dlat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c
