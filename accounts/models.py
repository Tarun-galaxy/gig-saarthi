"""Accounts app — Custom User model and PhoneVerification for Gig Saarthi."""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user model with role-based access for the cooperative platform."""

    ROLE_CHOICES = [
        ('worker', 'Worker'),
        ('customer', 'Customer'),
        ('coop_admin', 'Cooperative Admin'),
        ('platform_admin', 'Platform Admin'),
    ]

    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('hi', 'Hindi'),
        ('bn', 'Bengali'),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='customer',
        help_text="User role in the platform"
    )
    phone_number = models.CharField(
        max_length=15,
        unique=True,
        help_text="Phone number used for OTP verification"
    )
    preferred_language = models.CharField(
        max_length=10,
        choices=LANGUAGE_CHOICES,
        default='en',
        help_text="Preferred UI language"
    )
    is_phone_verified = models.BooleanField(
        default=False,
        help_text="Whether the phone number has been verified via OTP"
    )
    profile_photo = models.ImageField(
        upload_to='profiles/',
        blank=True,
        null=True,
        help_text="User profile photo"
    )

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def is_worker(self):
        return self.role == 'worker'

    @property
    def is_customer(self):
        return self.role == 'customer'

    @property
    def is_coop_admin(self):
        return self.role == 'coop_admin'

    @property
    def is_platform_admin(self):
        return self.role == 'platform_admin'

    @property
    def photo_url(self):
        if self.profile_photo:
            url = str(self.profile_photo)
            if url.startswith('http://') or url.startswith('https://'):
                return url
            try:
                return self.profile_photo.url
            except Exception:
                return f"/media/{url}"
        name = self.get_full_name() or self.username
        return f"https://ui-avatars.com/api/?name={name.replace(' ', '+')}&background=4f46e5&color=fff&bold=true&size=128"



class PhoneVerification(models.Model):
    """
    Tracks OTP verification attempts for phone numbers.
    Stores hashed OTP (not raw) for security.
    """

    PURPOSE_CHOICES = [
        ('verification', 'Phone Verification'),
        ('login', 'Login OTP'),
        ('password_reset', 'Password Reset'),
    ]

    phone_number = models.CharField(max_length=15, db_index=True)
    otp_hash = models.CharField(max_length=64, help_text="SHA-256 hash of the OTP")
    purpose = models.CharField(
        max_length=20,
        choices=PURPOSE_CHOICES,
        default='verification'
    )
    is_used = models.BooleanField(default=False)
    attempts = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Phone Verification'
        verbose_name_plural = 'Phone Verifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone_number', 'purpose', 'is_used']),
        ]

    def __str__(self):
        return f"OTP for {self.phone_number} ({self.purpose})"

    @property
    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        from django.utils import timezone
        return not self.is_used and not self.is_expired and self.attempts < 3
