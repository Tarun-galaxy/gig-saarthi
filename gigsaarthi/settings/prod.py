"""
Production settings for Gig Saarthi.
Usage: DJANGO_SETTINGS_MODULE=gigsaarthi.settings.prod
"""

from .base import *  # noqa: F401,F403

DEBUG = False

# Allowed hosts & CSRF for Render
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='*,gig-saarthi.onrender.com,.onrender.com,localhost,127.0.0.1', cast=Csv())
CSRF_TRUSTED_ORIGINS = [
    'https://*.onrender.com',
    'https://gig-saarthi.onrender.com',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]

# Security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = 'DENY'

# WhiteNoise
WHITENOISE_USE_FINDERS = True

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}
