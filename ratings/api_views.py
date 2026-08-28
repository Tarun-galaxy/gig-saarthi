"""Ratings API views for DRF."""

from rest_framework import generics, permissions
from rest_framework.response import Response
from .models import Review
from .serializers import ReviewSerializer, ReviewCreateSerializer


class ReviewListView(generics.ListAPIView):
    """List reviews given by or received by the current user."""

    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'worker':
            return Review.objects.filter(worker=user)
        elif user.role == 'customer':
            return Review.objects.filter(customer=user)
        return Review.objects.all()


class ReviewCreateView(generics.CreateAPIView):
    """Create a review for a completed booking."""

    serializer_class = ReviewCreateSerializer
    permission_classes = [permissions.IsAuthenticated]


class WorkerReviewsView(generics.ListAPIView):
    """List all public reviews for a specific worker."""

    serializer_class = ReviewSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        worker_id = self.kwargs['worker_id']
        return Review.objects.filter(
            worker_id=worker_id
        ).select_related('customer')
