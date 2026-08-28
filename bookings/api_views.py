"""Bookings API views for DRF."""

from django.db import models
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Booking, ServiceCategory
from .serializers import (
    BookingSerializer, BookingCreateSerializer,
    ServiceCategorySerializer
)


class ServiceCategoryListView(generics.ListAPIView):
    """List all active service categories."""

    queryset = ServiceCategory.objects.filter(is_active=True)
    serializer_class = ServiceCategorySerializer
    permission_classes = [permissions.AllowAny]


class BookingListView(generics.ListAPIView):
    """List bookings for the authenticated user."""

    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'worker':
            return Booking.objects.filter(worker=user).select_related(
                'customer', 'service_category'
            )
        elif user.role == 'customer':
            return Booking.objects.filter(customer=user).select_related(
                'worker', 'service_category'
            )
        # Admin sees all
        return Booking.objects.select_related(
            'customer', 'worker', 'service_category'
        )

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        # Filter by status
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class BookingCreateView(generics.CreateAPIView):
    """Create a new booking (customers only)."""

    serializer_class = BookingCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        if self.request.user.role != 'customer':
            raise permissions.PermissionDenied("Only customers can create bookings.")
        serializer.save()


class BookingDetailView(generics.RetrieveAPIView):
    """View booking details."""

    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ('coop_admin', 'platform_admin'):
            return Booking.objects.all()
        return Booking.objects.filter(
            models.Q(customer=user) | models.Q(worker=user)
        )
