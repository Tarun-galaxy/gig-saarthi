"""
Validation utilities for Gig Saarthi.
Handles file upload validation, rate limiting, and input sanitization.
"""

import os
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


# ── File Upload Validation ────────────────────────────────────────

# Allowed file types for uploads
ALLOWED_DOCUMENT_TYPES = {
    'id_proof': {
        'extensions': ['.jpg', '.jpeg', '.png', '.pdf'],
        'max_size_mb': 5,
        'label': 'ID Proof',
    },
    'certificate': {
        'extensions': ['.jpg', '.jpeg', '.png', '.pdf'],
        'max_size_mb': 10,
        'label': 'Certificate',
    },
    'profile_photo': {
        'extensions': ['.jpg', '.jpeg', '.png', '.webp'],
        'max_size_mb': 2,
        'label': 'Profile Photo',
    },
}


def validate_file_upload(file, upload_type='id_proof'):
    """
    Validate an uploaded file.
    
    Args:
        file: Django UploadedFile object
        upload_type: One of 'id_proof', 'certificate', 'profile_photo'
    
    Returns:
        (is_valid: bool, error_message: str)
    """
    if not file:
        return True, ''

    config = ALLOWED_DOCUMENT_TYPES.get(upload_type, ALLOWED_DOCUMENT_TYPES['id_proof'])

    # Check file extension
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in config['extensions']:
        return False, (
            f"Invalid file type '{ext}'. "
            f"Allowed: {', '.join(config['extensions'])}"
        )

    # Check file size
    max_size_bytes = config['max_size_mb'] * 1024 * 1024
    if file.size > max_size_bytes:
        return False, (
            f"File too large ({file.size / 1024 / 1024:.1f}MB). "
            f"Maximum allowed: {config['max_size_mb']}MB"
        )

    # Check for potentially dangerous files (basic)
    dangerous_patterns = ['.exe', '.bat', '.cmd', '.sh', '.php', '.js']
    if ext in dangerous_patterns:
        return False, "This file type is not allowed for security reasons"

    return True, ''


def sanitize_filename(filename):
    """
    Sanitize a filename to prevent path traversal and special characters.
    """
    # Remove path components
    filename = os.path.basename(filename)

    # Replace dangerous characters
    dangerous_chars = ['..', '/', '\\', '\x00']
    for char in dangerous_chars:
        filename = filename.replace(char, '_')

    # Limit length
    name, ext = os.path.splitext(filename)
    if len(name) > 100:
        name = name[:100]

    return f"{name}{ext}"


# ── Rate Limiting (Simple In-Memory) ───────────────────────────────

# In-memory rate limit store (for prototype — use Redis in production)
_rate_limits = {}


def check_rate_limit(key, max_requests=10, window_seconds=60):
    """
    Simple in-memory rate limiter.
    
    Args:
        key: Unique identifier (e.g., 'login:192.168.1.1')
        max_requests: Max requests allowed in the window
        window_seconds: Time window in seconds
    
    Returns:
        (allowed: bool, remaining: int, retry_after: int)
    """
    import time

    now = time.time()
    window_start = now - window_seconds

    if key not in _rate_limits:
        _rate_limits[key] = []

    # Clean old entries
    _rate_limits[key] = [t for t in _rate_limits[key] if t > window_start]

    current_count = len(_rate_limits[key])

    if current_count >= max_requests:
        oldest = _rate_limits[key][0]
        retry_after = int(oldest + window_seconds - now) + 1
        return False, 0, max(1, retry_after)

    _rate_limits[key].append(now)
    return True, max_requests - current_count - 1, 0


def rate_limit_key(request, prefix='api'):
    """Generate a rate limit key from a request."""
    ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
    if not ip:
        ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
    return f"{prefix}:{ip}"


# ── Input Validation ───────────────────────────────────────────────

def validate_phone_number(phone):
    """Validate Indian phone number format."""
    import re
    # Allow +91 prefix or 10-digit number
    pattern = r'^(\+91)?[6-9]\d{9}$'
    phone = phone.replace(' ', '').replace('-', '')
    return bool(re.match(pattern, phone))


def validate_otp(otp):
    """Validate OTP format (6 digits)."""
    return otp and otp.isdigit() and len(otp) == 6


def sanitize_text(text, max_length=5000):
    """Sanitize user text input."""
    if not text:
        return ''
    # Remove null bytes
    text = text.replace('\x00', '')
    # Trim to max length
    return text[:max_length].strip()
