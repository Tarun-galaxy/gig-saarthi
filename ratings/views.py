"""Ratings web views — Submit and view reviews."""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models.signals import post_save
from django.dispatch import receiver
from bookings.models import Booking
from .models import Review


@login_required
def submit_review(request, booking_id):
    """Submit a review for a completed booking."""
    booking = get_object_or_404(
        Booking, pk=booking_id,
        customer=request.user,
        status='completed'
    )

    # Check if already reviewed
    if Review.objects.filter(booking=booking).exists():
        messages.warning(request, 'You have already reviewed this booking.')
        return redirect('bookings:detail', pk=booking_id)

    if request.method == 'POST':
        overall_rating = int(request.POST.get('overall_rating', 5))
        punctuality_rating = request.POST.get('punctuality_rating')
        quality_rating = request.POST.get('quality_rating')
        comment = request.POST.get('comment', '')

        review = Review.objects.create(
            booking=booking,
            customer=request.user,
            worker=booking.worker,
            overall_rating=overall_rating,
            punctuality_rating=int(punctuality_rating) if punctuality_rating else None,
            quality_rating=int(quality_rating) if quality_rating else None,
            comment=comment,
        )

        # Update worker's average rating
        update_worker_rating(booking.worker)

        messages.success(request, 'Thank you for your review!')
        return redirect('bookings:detail', pk=booking_id)

    return render(request, 'ratings/submit_review.html', {'booking': booking})


def update_worker_rating(worker):
    """Recalculate and update a worker's average rating."""
    from workers.models import WorkerProfile
    from django.db.models import Avg, Count

    reviews = Review.objects.filter(worker=worker)
    stats = reviews.aggregate(
        avg=Avg('overall_rating'),
        count=Count('id')
    )

    try:
        profile = worker.worker_profile
        profile.avg_rating = stats['avg'] or 0
        profile.total_reviews = stats['count']
        profile.save(update_fields=['avg_rating', 'total_reviews'])
    except WorkerProfile.DoesNotExist:
        pass


# Signal to update worker rating when a review is saved
@receiver(post_save, sender=Review)
def on_review_created(sender, instance, created, **kwargs):
    """Auto-update worker rating when a new review is created."""
    if created:
        update_worker_rating(instance.worker)
