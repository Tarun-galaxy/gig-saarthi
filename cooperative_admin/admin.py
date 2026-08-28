"""Cooperative Admin — Register Cooperative model."""

from django.contrib import admin
from .models import Cooperative


@admin.register(Cooperative)
class CooperativeAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'region', 'district', 'state',
        'federation_level', 'worker_count', 'is_active', 'established_date'
    )
    list_filter = ('federation_level', 'is_active', 'state', 'district')
    search_fields = ('name', 'region', 'contact_person')
    readonly_fields = ('created_at', 'updated_at')
