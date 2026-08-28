"""Customers admin — Register customer-related models."""

from django.contrib import admin
from .models import CustomerProfile, SavedLocation


class SavedLocationInline(admin.TabularInline):
    model = SavedLocation
    extra = 0


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'default_address', 'created_at')
    search_fields = (
        'user__username', 'user__first_name', 'user__last_name',
        'user__phone_number'
    )
    inlines = [SavedLocationInline]


@admin.register(SavedLocation)
class SavedLocationAdmin(admin.ModelAdmin):
    list_display = ('label', 'customer', 'is_default', 'created_at')
    list_filter = ('is_default',)
    search_fields = ('label', 'address')
