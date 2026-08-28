"""Workers admin — Register worker-related models."""

from django.contrib import admin
from .models import SkillCategory, Skill, WorkerProfile, Certification, WorkerInsurance


class SkillInline(admin.TabularInline):
    model = Skill
    extra = 1


@admin.register(SkillCategory)
class SkillCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon', 'skill_count', 'created_at')
    search_fields = ('name',)
    inlines = [SkillInline]

    def skill_count(self, obj):
        return obj.skills.count()
    skill_count.short_description = 'Skills'


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'created_at')
    list_filter = ('category',)
    search_fields = ('name',)


@admin.register(WorkerProfile)
class WorkerProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'availability_status', 'is_verified',
        'cooperative', 'avg_rating', 'total_jobs_completed',
        'experience_years', 'created_at'
    )
    list_filter = (
        'availability_status', 'is_verified',
        'cooperative', 'skills'
    )
    search_fields = (
        'user__username', 'user__first_name', 'user__last_name',
        'user__phone_number', 'bio'
    )
    filter_horizontal = ('skills',)
    readonly_fields = ('avg_rating', 'total_jobs_completed', 'total_reviews')


@admin.register(Certification)
class CertificationAdmin(admin.ModelAdmin):
    list_display = (
        'certificate_name', 'worker', 'skill',
        'issued_by', 'is_verified', 'issue_date'
    )
    list_filter = ('is_verified', 'skill')
    search_fields = (
        'certificate_name', 'worker__user__username',
        'issued_by'
    )


@admin.register(WorkerInsurance)
class WorkerInsuranceAdmin(admin.ModelAdmin):
    list_display = (
        'worker', 'policy_number', 'provider',
        'coverage_type', 'status', 'valid_till', 'is_currently_valid'
    )
    list_filter = ('status', 'coverage_type')
    search_fields = (
        'policy_number', 'worker__user__username', 'provider'
    )
