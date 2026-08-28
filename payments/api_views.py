"""Payments API views for DRF."""

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from django.utils import timezone
from .models import Invoice, WorkerPayout


class InvoiceListView(generics.ListAPIView):
    """List invoices for the authenticated user."""

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'worker':
            return Invoice.objects.filter(booking__worker=user)
        elif user.role == 'customer':
            return Invoice.objects.filter(booking__customer=user)
        return Invoice.objects.all()

    def list(self, request, *args, **kwargs):
        from .serializers import InvoiceSerializer
        queryset = self.get_queryset()
        serializer = InvoiceSerializer(queryset, many=True)
        return Response(serializer.data)


class InvoiceDetailView(generics.RetrieveAPIView):
    """View invoice details."""

    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        from django.shortcuts import get_object_or_404
        return get_object_or_404(Invoice, pk=self.kwargs['pk'])

    def retrieve(self, request, *args, **kwargs):
        from .serializers import InvoiceSerializer
        instance = self.get_object()
        serializer = InvoiceSerializer(instance)
        return Response(serializer.data)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def payment_webhook_api(request):
    """Razorpay webhook endpoint for payment confirmation."""
    try:
        payload = request.data
        event = payload.get('event')

        if event == 'payment.captured':
            payment_entity = payload.get('payload', {}).get('payment', {}).get('entity', {})
            razorpay_order_id = payment_entity.get('order_id', '')
            razorpay_payment_id = payment_entity.get('id', '')

            try:
                invoice = Invoice.objects.get(razorpay_order_id=razorpay_order_id)
                invoice.razorpay_payment_id = razorpay_payment_id
                invoice.status = 'paid'
                invoice.paid_at = timezone.now()
                invoice.save()

                WorkerPayout.objects.create(
                    worker=invoice.booking.worker,
                    invoice=invoice,
                    amount=invoice.worker_payout,
                    status='pending'
                )
                return Response({'status': 'ok'})
            except Invoice.DoesNotExist:
                return Response(
                    {'status': 'error', 'message': 'Invoice not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

        return Response({'status': 'ignored'})
    except Exception as e:
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
