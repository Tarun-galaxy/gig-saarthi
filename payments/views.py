"""Payments web views — Razorpay checkout, webhooks, invoice management, worker payouts."""

import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from decimal import Decimal

from .models import Invoice, WorkerPayout
from bookings.models import Booking, BookingStatusHistory
from notifications.models import Notification
from core.services.razorpay_service import (
    create_order, verify_payment, verify_webhook_signature, get_client_config
)

logger = logging.getLogger(__name__)


# ── Invoice Views ──────────────────────────────────────────────────

@login_required
def invoice_list(request):
    """List invoices for the current user."""
    if request.user.role == 'worker':
        invoices = Invoice.objects.filter(
            booking__worker=request.user
        ).select_related('booking', 'booking__service_category')
    elif request.user.role == 'customer':
        invoices = Invoice.objects.filter(
            booking__customer=request.user
        ).select_related('booking', 'booking__service_category')
    else:
        invoices = Invoice.objects.select_related(
            'booking', 'booking__service_category'
        )

    return render(request, 'payments/invoice_list.html', {'invoices': invoices})


@login_required
def invoice_detail(request, pk):
    """View invoice details."""
    invoice = get_object_or_404(
        Invoice.objects.select_related(
            'booking', 'booking__customer', 'booking__worker',
            'booking__service_category', 'booking__worker__worker_profile'
        ),
        pk=pk
    )

    user = request.user
    if user not in (invoice.booking.customer, invoice.booking.worker) and \
       user.role not in ('coop_admin', 'platform_admin'):
        messages.error(request, 'You do not have access to this invoice.')
        return redirect('payments:list')

    return render(request, 'payments/invoice_detail.html', {'invoice': invoice})


# ── Razorpay Checkout Flow ─────────────────────────────────────────

@login_required
def initiate_payment(request, booking_id):
    """
    Initiate Razorpay payment for a completed booking.
    
    Flow:
    1. Verify booking is completed and belongs to customer
    2. Ensure invoice exists with correct pricing
    3. Create Razorpay order
    4. Show checkout page with Razorpay button
    """
    booking = get_object_or_404(
        Booking.objects.select_related('service_category', 'worker'),
        pk=booking_id,
        customer=request.user,
        status='completed'
    )

    # Get or create invoice
    invoice = Invoice.objects.filter(booking=booking).first()
    if not invoice:
        invoice = Invoice(booking=booking)
        amount = booking.final_price or booking.estimated_price or Decimal('0')
        invoice.amount = amount
        invoice.calculate_splits()
        invoice.save()

    # Check if already paid
    if invoice.status == 'paid':
        messages.info(request, 'This booking has already been paid for.')
        return redirect('payments:invoice_detail', pk=invoice.pk)

    # Create Razorpay order
    razorpay_config = get_client_config()
    order = create_order(
        amount=invoice.amount,
        receipt=f'booking_{booking.pk}',
        notes={
            'booking_id': str(booking.pk),
            'customer': request.user.username,
            'service': booking.service_category.name,
        }
    )

    if order:
        invoice.razorpay_order_id = order['id']
        invoice.save(update_fields=['razorpay_order_id'])

    context = {
        'invoice': invoice,
        'booking': booking,
        'order': order,
        'razorpay_key_id': razorpay_config['key_id'],
        'is_demo': razorpay_config['is_demo'],
        'amount_paise': int(invoice.amount * 100),
        'customer_email': request.user.email or f'{request.user.username}@gigsaarthi.in',
        'customer_phone': request.user.phone_number,
        'customer_name': request.user.get_full_name() or request.user.username,
    }
    return render(request, 'payments/payment_checkout.html', context)


@login_required
def payment_verify(request):
    """
    Verify Razorpay payment after checkout callback.
    Called from frontend JavaScript after successful payment.
    
    POST: {razorpay_order_id, razorpay_payment_id, razorpay_signature}
    """
    if request.method != 'POST':
        return redirect('payments:list')

    razorpay_order_id = request.POST.get('razorpay_order_id', '').strip()
    razorpay_payment_id = request.POST.get('razorpay_payment_id', '').strip()
    razorpay_signature = request.POST.get('razorpay_signature', '').strip()

    # Find the invoice by razorpay_order_id with fallback
    invoice = None
    if razorpay_order_id:
        invoice = Invoice.objects.filter(razorpay_order_id=razorpay_order_id).first()
    if not invoice:
        invoice = Invoice.objects.filter(
            booking__customer=request.user, 
            status__in=['pending', 'failed']
        ).order_by('-created_at').first()

    if not invoice:
        messages.error(request, 'Invoice not found for this transaction.')
        return redirect('payments:list')

    # Verify the payment signature
    is_valid = verify_payment(razorpay_order_id, razorpay_payment_id, razorpay_signature)

    if is_valid:
        # Update invoice
        invoice.razorpay_payment_id = razorpay_payment_id
        invoice.razorpay_signature = razorpay_signature
        invoice.status = 'paid'
        invoice.paid_at = timezone.now()
        invoice.save(update_fields=[
            'razorpay_payment_id', 'razorpay_signature',
            'status', 'paid_at', 'updated_at'
        ])

        # Create worker payout record
        _create_worker_payout(invoice)

        # Notify customer
        Notification.objects.create(
            user=invoice.booking.customer,
            title='Payment Successful!',
            message=f'Payment of Rs.{invoice.amount} for {invoice.booking.service_category.name} has been processed.',
            notification_type='payment_received',
            related_booking=invoice.booking,
        )

        # Notify worker
        if invoice.booking.worker:
            Notification.objects.create(
                user=invoice.booking.worker,
                title='Payment Received!',
                message=f'Payment of Rs.{invoice.worker_payout} for {invoice.booking.service_category.name} has been credited.',
                notification_type='payment_received',
                related_booking=invoice.booking,
            )

        messages.success(request, f'Payment of Rs.{invoice.amount} successful! Thank you.')
        return redirect('payments:success')
    else:
        invoice.status = 'failed'
        invoice.save(update_fields=['status', 'updated_at'])
        messages.error(request, 'Payment verification failed. Please try again.')
        return redirect('payments:invoice_detail', pk=invoice.pk)


@login_required
def payment_success(request):
    """Payment success page after Razorpay redirect."""
    # Get the latest paid invoice for this user
    latest_invoice = Invoice.objects.filter(
        booking__customer=request.user,
        status='paid'
    ).order_by('-paid_at').first()

    context = {
        'invoice': latest_invoice,
    }
    return render(request, 'payments/payment_success.html', context)


@login_required
def payment_failed(request):
    """Payment failure page."""
    booking_id = request.GET.get('booking_id')
    booking = None
    if booking_id:
        booking = Booking.objects.filter(pk=booking_id, customer=request.user).first()
    if not booking:
        # Fallback: get the most recent completed booking that is still unpaid
        booking = Booking.objects.filter(customer=request.user, status='completed').order_by('-created_at').first()

    messages.error(request, 'Payment was not completed. Please try again.')
    return render(request, 'payments/payment_failed.html', {'booking': booking})


# ── Webhook Endpoint ───────────────────────────────────────────────

@csrf_exempt
@require_POST
def payment_webhook(request):
    """
    Razorpay webhook endpoint for payment confirmation.
    Handles payment.captured and payment.failed events.
    
    Security: Verifies webhook signature before processing.
    """
    # Get signature from header
    signature = request.headers.get('X-Razorpay-Signature', '')
    payload_body = request.body

    # Verify webhook signature
    if not verify_webhook_signature(payload_body, signature):
        logger.warning("Webhook signature verification failed")
        return JsonResponse({'status': 'error', 'message': 'Invalid signature'}, status=400)

    try:
        payload = json.loads(payload_body)
        event = payload.get('event')

        if event == 'payment.captured':
            return _handle_payment_captured(payload)
        elif event == 'payment.failed':
            return _handle_payment_failed(payload)
        else:
            logger.info(f"Webhook: Ignoring event '{event}'")
            return JsonResponse({'status': 'ignored'})

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def _handle_payment_captured(payload):
    """Handle payment.captured webhook event."""
    payment_entity = payload.get('payload', {}).get('payment', {}).get('entity', {})
    razorpay_payment_id = payment_entity.get('id', '')
    razorpay_order_id = payment_entity.get('order_id', '')

    if not razorpay_order_id:
        return JsonResponse({'status': 'error', 'message': 'No order_id'}, status=400)

    try:
        invoice = Invoice.objects.get(razorpay_order_id=razorpay_order_id)
    except Invoice.DoesNotExist:
        logger.warning(f"Webhook: Invoice not found for order {razorpay_order_id}")
        return JsonResponse({'status': 'error', 'message': 'Invoice not found'}, status=404)

    # Update invoice
    invoice.razorpay_payment_id = razorpay_payment_id
    invoice.razorpay_signature = payment_entity.get('signature', '')
    invoice.status = 'paid'
    invoice.paid_at = timezone.now()
    invoice.save(update_fields=[
        'razorpay_payment_id', 'razorpay_signature',
        'status', 'paid_at', 'updated_at'
    ])

    # Create worker payout
    _create_worker_payout(invoice)

    # Notify
    Notification.objects.create(
        user=invoice.booking.customer,
        title='Payment Confirmed',
        message=f'Your payment of Rs.{invoice.amount} has been confirmed.',
        notification_type='payment_received',
        related_booking=invoice.booking,
    )

    logger.info(f"Webhook: Payment captured for invoice #{invoice.pk}")
    return JsonResponse({'status': 'ok'})


def _handle_payment_failed(payload):
    """Handle payment.failed webhook event."""
    payment_entity = payload.get('payload', {}).get('payment', {}).get('entity', {})
    razorpay_order_id = payment_entity.get('order_id', '')

    if razorpay_order_id:
        invoice = Invoice.objects.filter(razorpay_order_id=razorpay_order_id).first()
        if invoice:
            invoice.status = 'failed'
            invoice.save(update_fields=['status', 'updated_at'])

            Notification.objects.create(
                user=invoice.booking.customer,
                title='Payment Failed',
                message=f'Your payment of Rs.{invoice.amount} could not be processed. Please try again.',
                notification_type='payment_failed',
                related_booking=invoice.booking,
            )

            logger.info(f"Webhook: Payment failed for invoice #{invoice.pk}")

    return JsonResponse({'status': 'ok'})


# ── Worker Payout ──────────────────────────────────────────────────

def _create_worker_payout(invoice):
    """
    Create a WorkerPayout record after successful payment.
    In production, this would also trigger a bank/UPI transfer.
    """
    if not invoice.booking.worker:
        logger.warning(f"Invoice #{invoice.pk}: No worker assigned — skipping payout")
        return None

    payout, created = WorkerPayout.objects.get_or_create(
        worker=invoice.booking.worker,
        invoice=invoice,
        defaults={
            'amount': invoice.worker_payout,
            'status': 'pending',
        }
    )

    if created:
        logger.info(
            f"Payout #{payout.pk} created: Rs.{invoice.worker_payout} "
            f"to {invoice.booking.worker.get_full_name()}"
        )

    return payout


# ── Demo Payment (for testing without Razorpay keys) ───────────────

@login_required
def demo_payment(request, booking_id):
    """
    Simulate a successful payment for testing and sandbox development.
    Executes the full settlement, 95/5 split, and notifications.
    """
    booking = get_object_or_404(
        Booking, pk=booking_id, customer=request.user, status='completed'
    )

    import time
    demo_order_id = f"order_sandbox_{int(time.time())}"
    demo_payment_id = f"pay_sandbox_{int(time.time())}"

    invoice = Invoice.objects.filter(booking=booking).first()
    if not invoice:
        invoice = Invoice(booking=booking)
        amount = booking.final_price or booking.estimated_price or Decimal('0')
        invoice.amount = amount
        invoice.calculate_splits()

    invoice.razorpay_order_id = invoice.razorpay_order_id or demo_order_id
    invoice.razorpay_payment_id = demo_payment_id
    invoice.razorpay_signature = 'sandbox_verified_signature'
    invoice.status = 'paid'
    invoice.paid_at = timezone.now()
    invoice.save()

    # Create worker payout record
    _create_worker_payout(invoice)

    # Notifications
    Notification.objects.create(
        user=invoice.booking.customer,
        title='Payment Successful!',
        message=f'Payment of Rs.{invoice.amount} for {invoice.booking.service_category.name} has been processed.',
        notification_type='payment_received',
        related_booking=invoice.booking,
    )
    if invoice.booking.worker:
        Notification.objects.create(
            user=invoice.booking.worker,
            title='Payment Received!',
            message=f'Payment of Rs.{invoice.worker_payout} for {invoice.booking.service_category.name} has been credited.',
            notification_type='payment_received',
            related_booking=invoice.booking,
        )

    messages.success(request, f'Sandbox payment of Rs.{invoice.amount} authorized and settled!')
    return redirect('payments:success')

    # Create worker payout
    _create_worker_payout(invoice)

    # Notify
    Notification.objects.create(
        user=booking.customer,
        title='Demo Payment Successful!',
        message=f'Demo payment of Rs.{invoice.amount} for {booking.service_category.name} completed.',
        notification_type='payment_received',
        related_booking=booking,
    )

    if booking.worker:
        Notification.objects.create(
            user=booking.worker,
            title='Demo Payment Received!',
            message=f'Demo payment of Rs.{invoice.worker_payout} credited to your account.',
            notification_type='payment_received',
            related_booking=booking,
        )

    messages.success(request, f'Demo payment of Rs.{invoice.amount} completed successfully!')
    return redirect('payments:success')
