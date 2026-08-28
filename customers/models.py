"""Customers app — Customer profile model."""

import json
from django.db import models
from core.models import TimeStampedModel


class CustomerProfile(TimeStampedModel):
    """Extended profile for customers — linked one-to-one with User."""

    user = models.OneToOneField(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='customer_profile'
    )
    default_address = models.TextField(
        blank=True,
        default='',
        help_text="Default service address"
    )
    default_latitude = models.FloatField(
        default=0.0,
        help_text="Default address latitude"
    )
    default_longitude = models.FloatField(
        default=0.0,
        help_text="Default address longitude"
    )

    class Meta:
        verbose_name = 'Customer Profile'
        verbose_name_plural = 'Customer Profiles'

    def __str__(self):
        return f"Customer: {self.user.get_full_name() or self.user.username}"


class SavedLocation(TimeStampedModel):
    """Saved locations for a customer (home, work, etc.)."""

    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name='saved_locations'
    )
    label = models.CharField(
        max_length=50,
        help_text="Label like 'Home', 'Office', 'Parents' house'"
    )
    address = models.TextField(help_text="Full text address")
    latitude = models.FloatField(default=0.0)
    longitude = models.FloatField(default=0.0)
    is_default = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Saved Location'
        verbose_name_plural = 'Saved Locations'
        ordering = ['-is_default', 'label']

    def __str__(self):
        return f"{self.label}: {self.address[:50]}"
