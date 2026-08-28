"""
OTP Service for Gig Saarthi.
Handles OTP generation, sending (stub), and verification.

In production, replace the send_otp function with a real SMS gateway
(Twilio, MSG91, etc.). For the prototype, OTP is printed to console.
"""

import random
import hashlib
import time
from datetime import timedelta
from django.conf import settings
from django.utils import timezone


# OTP configuration
OTP_LENGTH = 6
OTP_EXPIRY_MINUTES = 5
MAX_OTP_ATTEMPTS = 3


def generate_otp():
    """Generate a random 6-digit OTP."""
    return ''.join([str(random.randint(0, 9)) for _ in range(OTP_LENGTH)])


def get_otp_hash(otp_code):
    """
    Create a one-way hash of the OTP for secure storage.
    We store the hash, not the raw OTP.
    """
    salt = getattr(settings, 'OTP_SALT', 'gigsaarthi-otp-salt')
    return hashlib.sha256(f"{salt}{otp_code}".encode()).hexdigest()


def send_otp(phone_number, otp_code, purpose='verification'):
    """
    Send OTP to the given phone number.
    
    STUB IMPLEMENTATION: Prints OTP to console.
    Replace with real SMS gateway in production.
    """
    purpose_labels = {
        'verification': 'Phone Verification',
        'login': 'Login',
        'password_reset': 'Password Reset',
    }
    label = purpose_labels.get(purpose, 'OTP')

    import sys
    print("=" * 60, flush=True)
    print(f"  [OTP STUB] {label}", flush=True)
    print(f"  Phone: {phone_number}", flush=True)
    print(f"  OTP: {otp_code}", flush=True)
    print(f"  Expires in: {OTP_EXPIRY_MINUTES} minutes", flush=True)
    print("=" * 60, flush=True)
    sys.stdout.flush()

    # TODO: Replace with real SMS gateway
    # from twilio.rest import Client
    # client = Client(settings.TWILIO_SID, settings.TWILIO_AUTH_TOKEN)
    # client.messages.create(
    #     body=f"Your Gig Saarthi {label} code is: {otp_code}. Valid for {OTP_EXPIRY_MINUTES} minutes.",
    #     from_=settings.TWILIO_PHONE,
    #     to=phone_number
    # )

    return True


def verify_otp(phone_number, otp_code, purpose='verification'):
    """
    Verify an OTP code for a phone number.
    
    In dev mode (OTP_TO_CONSOLE=True), always accept '123456' as a shortcut.
    
    Returns: (success: bool, message: str)
    """
    from accounts.models import PhoneVerification

    # Dev shortcut: always accept 123456
    if getattr(settings, 'OTP_TO_CONSOLE', False) and otp_code == '123456':
        verification = PhoneVerification.objects.filter(
            phone_number=phone_number,
            purpose=purpose,
            is_used=False,
        ).order_by('-created_at').first()
        if verification:
            verification.is_used = True
            verification.verified_at = timezone.now()
            verification.save(update_fields=['is_used', 'verified_at'])
        return True, "OTP verified successfully."

    # Find the latest unexpired, unused OTP for this phone and purpose
    verification = PhoneVerification.objects.filter(
        phone_number=phone_number,
        purpose=purpose,
        is_used=False,
        expires_at__gt=timezone.now()
    ).order_by('-created_at').first()

    if not verification:
        return False, "No valid OTP found. Please request a new one."

    # Check attempt limit
    if verification.attempts >= MAX_OTP_ATTEMPTS:
        verification.is_used = True
        verification.save(update_fields=['is_used'])
        return False, "Maximum OTP attempts exceeded. Please request a new one."

    # Increment attempts
    verification.attempts += 1
    verification.save(update_fields=['attempts'])

    # Compare hashes
    provided_hash = get_otp_hash(otp_code)
    if provided_hash == verification.otp_hash:
        verification.is_used = True
        verification.verified_at = timezone.now()
        verification.save(update_fields=['is_used', 'verified_at'])
        return True, "OTP verified successfully."
    else:
        return False, f"Incorrect OTP. {MAX_OTP_ATTEMPTS - verification.attempts} attempts remaining."


def create_otp_verification(phone_number, purpose='verification'):
    """
    Create a new OTP verification record and send the OTP.
    
    Returns: (verification_id, otp_code)
    """
    from accounts.models import PhoneVerification

    # Invalidate any existing unused OTPs for this phone+purpose
    PhoneVerification.objects.filter(
        phone_number=phone_number,
        purpose=purpose,
        is_used=False
    ).update(is_used=True)

    # Generate new OTP
    otp_code = generate_otp()
    otp_hash = get_otp_hash(otp_code)

    # Create verification record
    verification = PhoneVerification.objects.create(
        phone_number=phone_number,
        otp_hash=otp_hash,
        purpose=purpose,
        expires_at=timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES),
    )

    # Send the OTP
    send_otp(phone_number, otp_code, purpose)

    return verification.id, otp_code


def is_phone_verified_recently(phone_number, within_minutes=30):
    """
    Check if a phone number was verified recently.
    Used to prevent OTP re-verification within a short window.
    """
    from accounts.models import PhoneVerification
    cutoff = timezone.now() - timedelta(minutes=within_minutes)
    return PhoneVerification.objects.filter(
        phone_number=phone_number,
        purpose='verification',
        is_used=True,
        verified_at__gte=cutoff
    ).exists()
