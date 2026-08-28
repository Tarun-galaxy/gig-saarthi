"""
Development settings for Gig Saarthi.
Usage: DJANGO_SETTINGS_MODULE=gigsaarthi.settings.dev
"""

from .base import *  # noqa: F401,F403

DEBUG = True

# Default to SQLite only if DATABASE_URL is not provided
if not config('DATABASE_URL', default=None):
    DATABASES['default']['ENGINE'] = 'django.db.backends.sqlite3'

# Toolbar for debugging (optional, uncomment if django-debug-toolbar is installed)
# INSTALLED_APPS += ['debug_toolbar']
# MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
# INTERNAL_IPS = ['127.0.0.1']

# Email backend — console for dev
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# CORS allow all in dev
CORS_ALLOW_ALL_ORIGINS = True

# Print OTP to console in dev (no real SMS)
OTP_TO_CONSOLE = True
