"""Bookings admin — Register booking-related models."""

from django.contrib import admin
from .models import ServiceCategory, Booking, BookingStatusHistory


class BookingStatusHistoryInline(admin.TabularInline):
    model = BookingStatusHistory
    extra = 0
    readonly_fields = ('status', 'changed_by', 'notes', 'created_at')


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'base_price', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    filter_horizontal = ('related_skills',)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'customer', 'worker', 'service_category',
        'status', 'is_emergency', 'estimated_price',
        'final_price', 'created_at'
    )
    list_filter = ('status', 'is_emergency', 'service_category')
    search_fields = (
        'customer__username', 'worker__username',
        'description', 'address_text'
    )
    readonly_fields = (
        'created_at', 'updated_at', 'matched_at',
        'accepted_at', 'completed_at', 'cancelled_at'
    )
    inlines = [BookingStatusHistoryInline]


@admin.register(BookingStatusHistory)
class BookingStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('booking', 'status', 'changed_by', 'created_at')
    list_filter = ('status',)
    search_fields = ('booking__id',)
