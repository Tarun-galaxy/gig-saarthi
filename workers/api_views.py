"""Workers API views for DRF."""

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import WorkerProfile, Skill
from .serializers import WorkerProfileSerializer, WorkerListSerializer


class WorkerListView(generics.ListAPIView):
    """List all verified workers with filtering and search."""

    queryset = WorkerProfile.objects.filter(
        user__is_active=True,
        is_verified=True
    ).select_related('user', 'cooperative').prefetch_related('skills')

    serializer_class = WorkerListSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['availability_status', 'cooperative']
    search_fields = ['user__first_name', 'user__last_name', 'bio']
    ordering_fields = ['avg_rating', 'total_jobs_completed', 'experience_years']
    ordering = ['-avg_rating']

    def get_queryset(self):
        queryset = super().get_queryset()
        # Filter by skill
        skill_name = self.request.query_params.get('skill')
        if skill_name:
            queryset = queryset.filter(skills__name__icontains=skill_name).distinct()

        # Filter by min rating
        min_rating = self.request.query_params.get('min_rating')
        if min_rating:
            queryset = queryset.filter(avg_rating__gte=float(min_rating))

        # Filter by skill category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(
                skills__category__name__icontains=category
            ).distinct()

        return queryset


class WorkerDetailView(generics.RetrieveAPIView):
    """Get detailed worker profile by ID."""

    queryset = WorkerProfile.objects.filter(
        user__is_active=True
    ).select_related('user', 'cooperative').prefetch_related('skills', 'certifications')

    serializer_class = WorkerProfileSerializer
    permission_classes = [permissions.AllowAny]


class MyWorkerProfileView(APIView):
    """Get or update the authenticated worker's own profile."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.role != 'worker':
            return Response(
                {"error": "Only workers can access this endpoint."},
                status=status.HTTP_403_FORBIDDEN
            )
        try:
            profile = request.user.worker_profile
            serializer = WorkerProfileSerializer(profile)
            return Response(serializer.data)
        except WorkerProfile.DoesNotExist:
            return Response(
                {"error": "Worker profile not found. Please complete onboarding."},
                status=status.HTTP_404_NOT_FOUND
            )

    def patch(self, request):
        if request.user.role != 'worker':
            return Response(
                {"error": "Only workers can access this endpoint."},
                status=status.HTTP_403_FORBIDDEN
            )
        profile, _ = WorkerProfile.objects.get_or_create(user=request.user)
        serializer = WorkerProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
