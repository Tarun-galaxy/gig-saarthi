"""Customers API views for DRF."""

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import CustomerProfile
from .serializers import CustomerProfileSerializer


class MyCustomerProfileView(APIView):
    """Get or update the authenticated customer's profile."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.role != 'customer':
            return Response(
                {"error": "Only customers can access this endpoint."},
                status=status.HTTP_403_FORBIDDEN
            )
        profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
        serializer = CustomerProfileSerializer(profile)
        return Response(serializer.data)

    def patch(self, request):
        if request.user.role != 'customer':
            return Response(
                {"error": "Only customers can access this endpoint."},
                status=status.HTTP_403_FORBIDDEN
            )
        profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
        serializer = CustomerProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
