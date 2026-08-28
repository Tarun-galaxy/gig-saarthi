"""Workers app — Models for worker profiles, skills, certifications, and insurance."""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import TimeStampedModel


class SkillCategory(TimeStampedModel):
    """Category of skills (e.g., Plumbing, Electrical, Cleaning)."""

    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text="Icon class name (e.g., for Font Awesome or emoji)"
    )
    description = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Skill Category'
        verbose_name_plural = 'Skill Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Skill(TimeStampedModel):
    """Specific skill within a category."""

    category = models.ForeignKey(
        SkillCategory,
        on_delete=models.CASCADE,
        related_name='skills'
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Skill'
        verbose_name_plural = 'Skills'
        ordering = ['category', 'name']
        unique_together = ['category', 'name']

    def __str__(self):
        return f"{self.name} ({self.category.name})"


class WorkerProfile(TimeStampedModel):
    """
    Extended profile for workers — linked one-to-one with User.
    Contains skills, location, KYC, bank details, and availability.
    """

    AVAILABILITY_CHOICES = [
        ('available', 'Available'),
        ('busy', 'Busy'),
        ('offline', 'Offline'),
    ]

    user = models.OneToOneField(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='worker_profile'
    )
    skills = models.ManyToManyField(
        Skill,
        blank=True,
        related_name='workers',
        help_text="Skills this worker possesses"
    )
    experience_years = models.PositiveIntegerField(
        default=0,
        help_text="Years of professional experience"
    )
    cooperative = models.ForeignKey(
        'cooperative_admin.Cooperative',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workers',
        help_text="The cooperative this worker belongs to"
    )
    bio = models.TextField(
        blank=True,
        default='',
        help_text="Short bio / description of services offered"
    )
    availability_status = models.CharField(
        max_length=20,
        choices=AVAILABILITY_CHOICES,
        default='offline',
        help_text="Current availability status"
    )

    # Location fields (lat/lng as FloatFields for simplicity — PostGIS PointField for production)
    current_latitude = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        help_text="Current latitude coordinate"
    )
    current_longitude = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
        help_text="Current longitude coordinate"
    )

    # Rating stats (denormalized for performance — updated via signals)
    avg_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    total_jobs_completed = models.PositiveIntegerField(default=0)
    total_reviews = models.PositiveIntegerField(default=0)

    # KYC and verification
    is_verified = models.BooleanField(
        default=False,
        help_text="Whether the worker's documents have been verified by cooperative admin"
    )
    verification_date = models.DateTimeField(blank=True, null=True)

    # KYC Documents
    id_proof_type = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text="Type of ID proof (Aadhaar, PAN, Voter ID, etc.)"
    )
    id_proof_file = models.FileField(
        upload_to='documents/id/',
        blank=True,
        null=True,
        help_text="Upload ID proof document"
    )

    # Bank details for payouts
    bank_account_number = models.CharField(
        max_length=20,
        blank=True,
        default='',
        help_text="Bank account number for payouts"
    )
    bank_ifsc_code = models.CharField(
        max_length=11,
        blank=True,
        default='',
        help_text="IFSC code for bank transfers"
    )
    bank_name = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Name of the bank"
    )
    upi_id = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text="UPI ID for payments"
    )

    class Meta:
        verbose_name = 'Worker Profile'
        verbose_name_plural = 'Worker Profiles'
        ordering = ['-avg_rating', '-total_jobs_completed']

    def __str__(self):
        return f"Worker: {self.user.get_full_name() or self.user.username}"

    @property
    def full_address(self):
        """Return formatted location string."""
        return f"({self.current_latitude}, {self.current_longitude})"

    @property
    def has_bank_details(self):
        return bool(self.bank_account_number and self.bank_ifsc_code)


class Certification(TimeStampedModel):
    """Worker certifications — uploaded documents verified by cooperative admin."""

    worker = models.ForeignKey(
        WorkerProfile,
        on_delete=models.CASCADE,
        related_name='certifications'
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.CASCADE,
        related_name='certifications',
        help_text="Skill this certification is for"
    )
    certificate_file = models.FileField(
        upload_to='documents/certificates/',
        help_text="Upload certificate document"
    )
    certificate_name = models.CharField(
        max_length=200,
        help_text="Name/title of the certification"
    )
    issued_by = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text="Organization that issued the certification"
    )
    issue_date = models.DateField(blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)

    is_verified = models.BooleanField(
        default=False,
        help_text="Verified by cooperative admin"
    )
    verified_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_certifications'
    )
    verification_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Certification'
        verbose_name_plural = 'Certifications'
        ordering = ['-issue_date']

    def __str__(self):
        return f"{self.certificate_name} — {self.worker}"


class WorkerInsurance(TimeStampedModel):
    """Insurance records for workers — enrolled by cooperative admin."""

    COVERAGE_TYPE_CHOICES = [
        ('accident', 'Accident Cover'),
        ('health', 'Health Cover'),
        ('life', 'Life Insurance'),
        ('combined', 'Combined Cover'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('pending', 'Pending Activation'),
        ('cancelled', 'Cancelled'),
    ]

    worker = models.ForeignKey(
        WorkerProfile,
        on_delete=models.CASCADE,
        related_name='insurance_policies'
    )
    policy_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Insurance policy number"
    )
    provider = models.CharField(
        max_length=200,
        help_text="Insurance provider name"
    )
    coverage_type = models.CharField(
        max_length=20,
        choices=COVERAGE_TYPE_CHOICES,
        help_text="Type of insurance coverage"
    )
    coverage_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Coverage amount in INR"
    )
    valid_from = models.DateField(
        help_text="Insurance validity start date"
    )
    valid_till = models.DateField(
        help_text="Insurance validity end date"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    enrolled_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='enrolled_insurances'
    )

    class Meta:
        verbose_name = 'Worker Insurance'
        verbose_name_plural = 'Worker Insurances'
        ordering = ['-valid_till']

    def __str__(self):
        return f"{self.get_coverage_type_display()} — {self.worker}"

    @property
    def is_currently_valid(self):
        """Check if insurance is currently valid."""
        from django.utils import timezone
        today = timezone.now().date()
        return self.status == 'active' and self.valid_from <= today <= self.valid_till
