"""Payments API views for DRF."""

from rest_framework import generics, permissions
from rest_framework.response import Response
from .models import Invoice


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

