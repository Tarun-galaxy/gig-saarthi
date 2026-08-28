"""Accounts admin — Register User model with useful admin configuration."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        'username', 'email', 'first_name', 'last_name',
        'role', 'phone_number', 'is_phone_verified',
        'preferred_language', 'is_active', 'date_joined'
    )
    list_filter = ('role', 'is_phone_verified', 'is_active', 'preferred_language')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone_number')
    ordering = ('-date_joined',)

    # Add role and phone fields to the admin user creation/edit forms
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Gig Saarthi Profile', {
            'fields': (
                'role', 'phone_number', 'preferred_language',
                'is_phone_verified', 'profile_photo'
            )
        }),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Gig Saarthi Profile', {
            'fields': ('role', 'phone_number')
        }),
    )
