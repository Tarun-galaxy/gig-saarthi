"""Ratings app — Review and rating model with breakdowns and flagging."""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import TimeStampedModel


class Review(TimeStampedModel):
    """Customer review and rating for a completed booking."""

    booking = models.OneToOneField(
        'bookings.Booking',
        on_delete=models.CASCADE,
        related_name='review'
    )
    customer = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='reviews_given'
    )
    worker = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='reviews_received'
    )

    overall_rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Overall rating (1-5 stars)"
    )
    punctuality_rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        blank=True, null=True,
        help_text="Punctuality rating (1-5 stars)"
    )
    quality_rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        blank=True, null=True,
        help_text="Quality of work rating (1-5 stars)"
    )
    comment = models.TextField(blank=True, default='')
    is_flagged = models.BooleanField(default=False)
    flag_reason = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        verbose_name = 'Review'
        verbose_name_plural = 'Reviews'
        ordering = ['-created_at']

    def __str__(self):
        return (
            f"Review by {self.customer.get_full_name()} for "
            f"{self.worker.get_full_name()}: {self.overall_rating} stars"
        )

    def save(self, *args, **kwargs):
        if self.overall_rating <= 2 and not self.is_flagged:
            self.is_flagged = True
            self.flag_reason = f"Low rating ({self.overall_rating} stars) — requires review"
        super().save(*args, **kwargs)

    @property
    def rating_stars(self):
        """Return star display string."""
        return '★' * self.overall_rating + '☆' * (5 - self.overall_rating)


class RatingStats:
    """
    Utility to calculate rating breakdowns for a worker.
    Not a model — used as a helper class.
    """

    @staticmethod
    def get_breakdown(worker):
        """
        Get rating breakdown for a worker.
        Returns dict with star distribution, averages, and total.
        """
        from django.db.models import Avg, Count, Q

        reviews = Review.objects.filter(worker=worker)
        stats = reviews.aggregate(
            avg_overall=Avg('overall_rating'),
            avg_punctuality=Avg('punctuality_rating'),
            avg_quality=Avg('quality_rating'),
            total=Count('id'),
        )

        # Star distribution (5,4,3,2,1)
        distribution = {}
        for star in range(5, 0, -1):
            count = reviews.filter(overall_rating=star).count()
            distribution[star] = count

        # Recent reviews
        recent = reviews.select_related('customer')[:5]

        return {
            'avg_overall': round(stats['avg_overall'] or 0, 1),
            'avg_punctuality': round(stats['avg_punctuality'] or 0, 1),
            'avg_quality': round(stats['avg_quality'] or 0, 1),
            'total_reviews': stats['total'],
            'distribution': distribution,
            'recent_reviews': recent,
            'flagged_count': reviews.filter(is_flagged=True).count(),
        }

    @staticmethod
    def get_worker_stats(worker):
        """Get simplified stats for worker profile display."""
        from django.db.models import Avg, Count
        stats = Review.objects.filter(worker=worker).aggregate(
            avg=Avg('overall_rating'),
            count=Count('id'),
        )
        return {
            'avg_rating': round(stats['avg'] or 0, 1),
            'total_reviews': stats['count'],
        }
