"""
Geo-Matching Engine for Gig Saarthi.

Finds the best nearby workers for a booking using:
1. Skill matching (worker skills ↔ service category)
2. Availability filter (only 'available' workers)
3. Verification filter (only verified workers)
4. Distance ranking via Haversine formula (primary)
5. Rating ranking (secondary tiebreaker)
6. Emergency weighting (distance weighted more heavily)

Production upgrade path: Replace Haversine with PostGIS ST_Distance
using GeoDjango PointField annotations.
"""

import math
import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q

logger = logging.getLogger(__name__)


# ── Configuration ──────────────────────────────────────────────────

# Maximum distance (km) to search for workers
MAX_SEARCH_RADIUS_KM = 50

# For emergency bookings, reduce radius for faster matching
EMERGENCY_SEARCH_RADIUS_KM = 15

# Number of top candidates to return
TOP_CANDIDATES = 5

# Accept timeout (seconds) — if worker doesn't respond, auto-reassign
ACCEPT_TIMEOUT_NORMAL = 300  # 5 minutes
ACCEPT_TIMEOUT_EMERGENCY = 60  # 1 minute for emergency


# ── Haversine Distance ─────────────────────────────────────────────

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance (in km) between two points
    on Earth using the Haversine formula.
    
    Args:
        lat1, lon1: Latitude and longitude of point 1 (degrees)
        lat2, lon2: Latitude and longitude of point 2 (degrees)
    
    Returns:
        Distance in kilometers (float)
    """
    R = 6371  # Earth's radius in kilometers

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (math.sin(dlat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


# ── Core Matching Functions ────────────────────────────────────────

def find_nearby_workers(booking, max_results=TOP_CANDIDATES):
    """
    Find the best nearby workers for a booking.
    
    Algorithm:
    1. Get workers matching the service category's required skills
    2. Filter: available, verified, not at max bookings
    3. Calculate distance from booking location
    4. Filter by max search radius
    5. Rank by: distance (primary), rating (secondary)
    6. Return top N candidates
    
    Args:
        booking: Booking instance with latitude, longitude, service_category
        max_results: Maximum number of candidates to return
    
    Returns:
        List of dicts: [{
            'worker': User instance,
            'worker_profile': WorkerProfile instance,
            'distance_km': float,
            'rating': float,
            'score': float (lower is better),
        }]
    """
    from workers.models import WorkerProfile

    # Determine search radius
    if booking.is_emergency:
        max_radius = EMERGENCY_SEARCH_RADIUS_KM
    else:
        max_radius = MAX_SEARCH_RADIUS_KM

    # Get skills required for this service category
    required_skills = booking.service_category.related_skills.all()
    skill_ids = [s.id for s in required_skills]

    # Base queryset: verified, available workers
    workers = WorkerProfile.objects.filter(
        is_verified=True,
        availability_status='available',
        user__is_active=True,
    ).select_related('user', 'cooperative').prefetch_related('skills')

    # Filter by skill match (workers must have at least one required skill)
    if skill_ids:
        workers = workers.filter(skills__id__in=skill_ids).distinct()

    # Filter out workers who already have a committed booking (accepted/in_progress)
    # Workers with 'matched' status can still take new jobs (they haven't accepted yet)
    from bookings.models import Booking
    committed_worker_ids = Booking.objects.filter(
        status__in=['accepted', 'in_progress'],
    ).exclude(
        id=booking.id
    ).values_list('worker_id', flat=True)

    workers = workers.exclude(user_id__in=committed_worker_ids)

    # Calculate distance and filter by radius
    candidates = []
    for worker in workers:
        distance = haversine_distance(
            booking.latitude, booking.longitude,
            worker.current_latitude, worker.current_longitude
        )

        if distance <= max_radius:
            # Calculate composite score (lower is better)
            # Distance weight: higher for emergency
            if booking.is_emergency:
                distance_weight = 0.8
                rating_weight = 0.2
            else:
                distance_weight = 0.6
                rating_weight = 0.4

            # Normalize distance to 0-1 range within max_radius
            normalized_distance = distance / max_radius

            # Normalize rating to 0-1 range (inverted: 5★ = 0, 1★ = 1)
            normalized_rating = (5 - float(worker.avg_rating)) / 4 if worker.avg_rating > 0 else 1

            score = (distance_weight * normalized_distance +
                     rating_weight * normalized_rating)

            candidates.append({
                'worker': worker.user,
                'worker_profile': worker,
                'distance_km': round(distance, 2),
                'rating': float(worker.avg_rating),
                'jobs_completed': worker.total_jobs_completed,
                'score': round(score, 4),
            })

    # Sort by score (lower is better)
    candidates.sort(key=lambda x: x['score'])

    return candidates[:max_results]


def find_and_assign_worker(booking):
    """
    Find the best worker for a booking and assign them.
    Sets booking status to 'matched' and notifies the worker.
    
    Args:
        booking: Booking instance (status must be 'pending')
    
    Returns:
        dict: {
            'success': bool,
            'worker': User instance or None,
            'candidates_count': int,
            'message': str,
        }
    """
    from bookings.models import BookingStatusHistory
    from notifications.models import Notification

    candidates = find_nearby_workers(booking)

    if not candidates:
        logger.info(f"No workers found for booking #{booking.pk}")
        return {
            'success': False,
            'worker': None,
            'candidates_count': 0,
            'message': 'No available workers found nearby. We are expanding the search.',
        }

    # Pick the best candidate
    best = candidates[0]
    worker = best['worker']

    # Assign worker
    booking.worker = worker
    booking.status = 'matched'
    booking.matched_at = timezone.now()
    booking.save(update_fields=['worker', 'status', 'matched_at', 'updated_at'])

    # Log status change
    BookingStatusHistory.objects.create(
        booking=booking,
        status='matched',
        changed_by=None,
        notes=f"Auto-matched to {worker.get_full_name()} ({best['distance_km']}km away, {best['rating']}★)"
    )

    # Notify the worker
    Notification.objects.create(
        user=worker,
        title=f'New Job Request: {booking.service_category.name}',
        message=(
            f"A customer needs {booking.service_category.name} at {booking.address_text}. "
            f"Scheduled: {booking.scheduled_datetime.strftime('%d %b, %I:%M %p')}. "
            f"Distance: {best['distance_km']}km."
        ),
        notification_type='booking_request',
        related_booking=booking,
    )

    logger.info(
        f"Booking #{booking.pk} matched to {worker.username} "
        f"({best['distance_km']}km, score={best['score']})"
    )

    return {
        'success': True,
        'worker': worker,
        'candidates_count': len(candidates),
        'message': f'Matched with {worker.get_full_name()} ({best["distance_km"]}km away)',
    }


def reassign_to_next_worker(booking, exclude_worker_ids=None):
    """
    When a worker rejects or times out, try the next available candidate.
    
    Args:
        booking: Booking instance
        exclude_worker_ids: Set of worker user IDs to exclude
    
    Returns:
        dict: Same as find_and_assign_worker
    """
    from bookings.models import BookingStatusHistory
    from notifications.models import Notification

    if exclude_worker_ids is None:
        exclude_worker_ids = set()

    # Get all candidates, excluding previously rejected/timed-out workers
    all_candidates = find_nearby_workers(booking, max_results=20)
    filtered = [c for c in all_candidates if c['worker'].id not in exclude_worker_ids]

    if not filtered:
        # No more candidates — try expanding the radius
        booking.status = 'pending'
        booking.worker = None
        booking.save(update_fields=['status', 'worker', 'updated_at'])

        BookingStatusHistory.objects.create(
            booking=booking,
            status='pending',
            notes='No more workers available — returned to pending pool'
        )

        Notification.objects.create(
            user=booking.customer,
            title='Searching for Workers',
            message='All nearby workers are busy. We are expanding the search radius.',
            notification_type='booking_request',
            related_booking=booking,
        )

        return {
            'success': False,
            'worker': None,
            'candidates_count': 0,
            'message': 'No more workers available. Expanding search.',
        }

    # Assign the next best candidate
    best = filtered[0]
    worker = best['worker']

    booking.worker = worker
    booking.status = 'matched'
    booking.matched_at = timezone.now()
    booking.save(update_fields=['worker', 'status', 'matched_at', 'updated_at'])

    # Log
    BookingStatusHistory.objects.create(
        booking=booking,
        status='matched',
        notes=f"Re-assigned to {worker.get_full_name()} after rejection/timeout"
    )

    # Notify
    Notification.objects.create(
        user=worker,
        title=f'New Job Request: {booking.service_category.name}',
        message=(
            f"A customer needs {booking.service_category.name} at {booking.address_text}. "
            f"Scheduled: {booking.scheduled_datetime.strftime('%d %b, %I:%M %p')}. "
            f"Distance: {best['distance_km']}km."
        ),
        notification_type='booking_request',
        related_booking=booking,
    )

    return {
        'success': True,
        'worker': worker,
        'candidates_count': len(filtered),
        'message': f'Re-assigned to {worker.get_full_name()}',
    }


def get_accept_timeout(booking):
    """Get the accept timeout duration for a booking."""
    if booking.is_emergency:
        return ACCEPT_TIMEOUT_EMERGENCY
    return ACCEPT_TIMEOUT_NORMAL


def get_matching_stats(booking):
    """
    Get matching statistics for a booking (useful for dashboard display).
    
    Returns:
        dict with matching details
    """
    candidates = find_nearby_workers(booking, max_results=20)

    return {
        'total_candidates': len(candidates),
        'booking_id': booking.pk,
        'is_emergency': booking.is_emergency,
        'search_radius_km': EMERGENCY_SEARCH_RADIUS_KM if booking.is_emergency else MAX_SEARCH_RADIUS_KM,
        'top_candidates': [
            {
                'name': c['worker'].get_full_name(),
                'distance_km': c['distance_km'],
                'rating': c['rating'],
                'score': c['score'],
            }
            for c in candidates[:5]
        ]
    }
