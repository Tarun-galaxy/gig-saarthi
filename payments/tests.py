import hashlib
import hmac
import json

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import WorkerPayout

SECRET = 'test_webhook_secret'


def _signed(body: bytes) -> str:
    return hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


@override_settings(RAZORPAY_KEY_SECRET=SECRET, RAZORPAY_WEBHOOK_SECRET=SECRET)
class PaymentWebhookApiTests(TestCase):
    """The API webhook route must use the same signed handler as the web route."""

    body = json.dumps({
        'event': 'payment.captured',
        'payload': {'payment': {'entity': {'id': 'pay_test_1', 'order_id': 'order_missing'}}},
    }).encode()

    def test_api_webhook_rejects_unsigned_requests(self):
        response = self.client.post(reverse('api:payments_api:webhook'), data=self.body, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(WorkerPayout.objects.count(), 0)

    def test_api_webhook_rejects_bad_signature(self):
        response = self.client.post(
            reverse('api:payments_api:webhook'), data=self.body, content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE='0' * 64,
        )
        self.assertEqual(response.status_code, 400)

    def test_api_webhook_accepts_signed_requests(self):
        response = self.client.post(
            reverse('api:payments_api:webhook'), data=self.body, content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE=_signed(self.body),
        )
        # Signature accepted; this order has no invoice
        self.assertEqual(response.status_code, 404)
