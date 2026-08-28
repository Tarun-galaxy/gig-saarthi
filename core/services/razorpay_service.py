"""
Razorpay Service for Gig Saarthi.
Handles order creation, payment verification, and webhook signature validation.

Uses Razorpay Test Mode keys for prototype.
Replace with production keys for live deployment.
"""

import hashlib
import hmac
import json
import logging
from decimal import Decimal
from django.conf import settings

logger = logging.getLogger(__name__)


def get_client():
    """
    Get a Razorpay client instance.
    Returns None if keys are not configured.
    """
    key_id = getattr(settings, 'RAZORPAY_KEY_ID', '')
    key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')

    if not key_id or not key_secret or key_id.startswith('rzp_test_xxx'):
        logger.warning("Razorpay keys not configured — using demo mode")
        return None

    try:
        import razorpay
        client = razorpay.Client(auth=(key_id, key_secret))
        return client
    except ImportError:
        logger.warning("razorpay package not installed — using demo mode")
        return None


def create_order(amount, receipt=None, notes=None):
    """
    Create a Razorpay order for the given amount.
    
    Args:
        amount: Decimal amount in INR
        receipt: Optional receipt string (booking ID recommended)
        notes: Optional dict of notes
    
    Returns:
        dict with order details or None if demo mode
    """
    client = get_client()

    # Convert to paise (Razorpay uses smallest currency unit)
    amount_paise = int(amount * 100)

    if client is None:
        # Demo mode — generate a mock order
        import time
        mock_order_id = f"order_demo_{int(time.time())}_{amount_paise}"
        logger.info(f"Demo mode: Created mock order {mock_order_id} for ₹{amount}")
        return {
            'id': mock_order_id,
            'amount': amount_paise,
            'currency': 'INR',
            'receipt': receipt or 'demo_receipt',
            'status': 'created',
            'notes': notes or {},
        }

    try:
        order_data = {
            'amount': amount_paise,
            'currency': 'INR',
            'receipt': receipt or f'booking_{receipt}',
            'notes': notes or {},
        }
        order = client.order.create(data=order_data)
        logger.info(f"Razorpay order created: {order['id']} for ₹{amount}")
        return order
    except Exception as e:
        logger.error(f"Razorpay order creation failed: {e}")
        return None


def verify_payment(razorpay_order_id, razorpay_payment_id, razorpay_signature):
    """
    Verify a Razorpay payment signature.
    
    Args:
        razorpay_order_id: The order ID
        razorpay_payment_id: The payment ID
        razorpay_signature: The signature from Razorpay
    
    Returns:
        bool: True if signature is valid
    """
    client = get_client()

    if client is None:
        # Demo mode — accept any payment with demo prefix
        if razorpay_payment_id.startswith('pay_demo_'):
            logger.info(f"Demo mode: Accepting payment {razorpay_payment_id}")
            return True
        logger.warning(f"Demo mode: Payment {razorpay_payment_id} doesn't look like a demo payment")
        return True  # Accept all in demo mode

    try:
        # Razorpay signature verification
        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature,
        }
        client.utility.verify_payment_signature(params_dict)
        logger.info(f"Payment verified: {razorpay_payment_id} for order {razorpay_order_id}")
        return True
    except Exception as e:
        logger.warning(f"SDK verification notice: {e}, verifying with direct HMAC-SHA256")
        # Manual HMAC verification fallback
        try:
            key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')
            msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode('utf-8')
            expected_sig = hmac.new(key_secret.encode('utf-8'), msg, hashlib.sha256).hexdigest()
            if hmac.compare_digest(expected_sig, razorpay_signature or ''):
                logger.info(f"HMAC verification succeeded: {razorpay_payment_id}")
                return True
        except Exception as err:
            logger.error(f"Manual HMAC verification error: {err}")

        logger.error(f"Payment verification failed: {e}")
        return False


def verify_webhook_signature(payload_body, signature, secret=None):
    """
    Verify Razorpay webhook signature.
    
    Args:
        payload_body: Raw request body (bytes or string)
        signature: X-Razorpay-Signature header value
        secret: Webhook secret (defaults to RAZORPAY_KEY_SECRET)
    
    Returns:
        bool: True if signature is valid
    """
    if secret is None:
        secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')

    if not secret:
        logger.warning("No webhook secret configured — accepting all webhooks")
        return True

    if isinstance(payload_body, str):
        payload_body = payload_body.encode('utf-8')

    try:
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload_body,
            hashlib.sha256
        ).hexdigest()

        is_valid = hmac.compare_digest(expected_signature, signature or '')
        if not is_valid:
            logger.warning("Webhook signature mismatch")
        return is_valid
    except Exception as e:
        logger.error(f"Webhook signature verification error: {e}")
        return False


def get_client_config():
    """
    Get Razorpay client configuration for frontend.
    Returns the key_id and demo mode flag.
    """
    key_id = getattr(settings, 'RAZORPAY_KEY_ID', '')
    is_demo = not key_id or key_id.startswith('rzp_test_xxx') or key_id == ''

    return {
        'key_id': key_id if not is_demo else 'rzp_test_demo',
        'is_demo': is_demo,
        'currency': 'INR',
    }
