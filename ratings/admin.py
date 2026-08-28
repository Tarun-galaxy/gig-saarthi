"""Ratings admin — Register Review model."""

from django.contrib import admin
from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        'booking', 'customer', 'worker',
        'overall_rating', 'punctuality_rating', 'quality_rating',
        'is_flagged', 'created_at'
    )
    list_filter = ('overall_rating', 'is_flagged')
    search_fields = (
        'customer__username', 'worker__username', 'comment'
    )
    readonly_fields = ('created_at',)
