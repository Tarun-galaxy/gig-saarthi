"""Workers serializers for DRF API."""

from rest_framework import serializers
from .models import SkillCategory, Skill, WorkerProfile, Certification, WorkerInsurance


class SkillSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Skill
        fields = ['id', 'name', 'category', 'category_name', 'description']


class SkillCategorySerializer(serializers.ModelSerializer):
    skills = SkillSerializer(many=True, read_only=True)
    skill_count = serializers.SerializerMethodField()

    class Meta:
        model = SkillCategory
        fields = ['id', 'name', 'icon', 'description', 'skills', 'skill_count']

    def get_skill_count(self, obj):
        return obj.skills.count()


class CertificationSerializer(serializers.ModelSerializer):
    skill_name = serializers.CharField(source='skill.name', read_only=True)

    class Meta:
        model = Certification
        fields = [
            'id', 'skill', 'skill_name', 'certificate_name',
            'certificate_file', 'issued_by', 'issue_date', 'expiry_date',
            'is_verified', 'verification_date'
        ]
        read_only_fields = ['is_verified', 'verification_date']


class WorkerProfileSerializer(serializers.ModelSerializer):
    """Full worker profile serializer for API responses."""

    username = serializers.CharField(source='user.username', read_only=True)
    full_name = serializers.SerializerMethodField()
    skills = SkillSerializer(many=True, read_only=True)
    certifications = CertificationSerializer(many=True, read_only=True)
    cooperative_name = serializers.CharField(
        source='cooperative.name', read_only=True, default=None
    )

    class Meta:
        model = WorkerProfile
        fields = [
            'id', 'username', 'full_name', 'skills', 'experience_years',
            'cooperative', 'cooperative_name', 'bio', 'availability_status',
            'current_latitude', 'current_longitude',
            'avg_rating', 'total_jobs_completed', 'total_reviews',
            'is_verified', 'certifications',
            'created_at'
        ]
        read_only_fields = [
            'avg_rating', 'total_jobs_completed', 'total_reviews',
            'is_verified', 'created_at'
        ]

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


class WorkerListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for worker listing."""

    full_name = serializers.SerializerMethodField()
    skills = SkillSerializer(many=True, read_only=True)

    class Meta:
        model = WorkerProfile
        fields = [
            'id', 'full_name', 'skills', 'experience_years',
            'availability_status', 'avg_rating', 'total_jobs_completed',
            'is_verified'
        ]

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


class WorkerInsuranceSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkerInsurance
        fields = [
            'id', 'policy_number', 'provider', 'coverage_type',
            'coverage_amount', 'valid_from', 'valid_till', 'status'
        ]
