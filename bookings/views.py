"""Bookings web views — Create, list, manage bookings with matching engine."""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from .models import Booking, ServiceCategory, BookingStatusHistory
from core.services.matching import (
    find_nearby_workers, find_and_assign_worker,
    reassign_to_next_worker, get_matching_stats
)
from notifications.models import Notification


@login_required
def booking_list(request):
    """List user's bookings based on role."""
    if request.user.role == 'worker':
        bookings = request.user.worker_bookings.select_related(
            'customer', 'service_category'
        )
    elif request.user.role == 'customer':
        bookings = request.user.customer_bookings.select_related(
            'worker', 'service_category'
        )
    else:
        bookings = Booking.objects.select_related(
            'customer', 'worker', 'service_category'
        )

    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        bookings = bookings.filter(status=status_filter)

    context = {
        'bookings': bookings,
        'status_filter': status_filter,
        'status_choices': Booking.STATUS_CHOICES,
    }
    return render(request, 'bookings/booking_list.html', context)


@login_required
def booking_create(request):
    """Create a new booking and trigger matching engine."""
    if request.user.role != 'customer':
        messages.warning(request, 'Only customers can create bookings.')
        return redirect('core:dashboard')

    categories = ServiceCategory.objects.filter(is_active=True)

    if request.method == 'POST':
        category_id = request.POST.get('service_category')
        description = request.POST.get('description', '')
        is_emergency = request.POST.get('is_emergency') == 'on'
        address_text = request.POST.get('address_text', '')
        latitude = float(request.POST.get('latitude', 0))
        longitude = float(request.POST.get('longitude', 0))

        # Combine date + time into scheduled_datetime
        booking_date = request.POST.get('date', '')
        booking_time = request.POST.get('time', '')
        scheduled_datetime = None
        if booking_date and booking_time:
            from django.utils.dateparse import parse_datetime
            scheduled_datetime = parse_datetime(f'{booking_date}T{booking_time}:00')
        if not scheduled_datetime:
            scheduled_datetime = timezone.now() + timezone.timedelta(hours=1)

        category = get_object_or_404(ServiceCategory, id=category_id)

        # Calculate 5% AI Demand Multiplier + Area Surge Charge (₹20 - ₹25)
        from decimal import Decimal, InvalidOperation
        demand_mult_amount = (category.base_price * Decimal('0.05')).quantize(Decimal('1'))
        # Determine area surge (₹25 for high density/metro zone, ₹20 for local neighborhood zone)
        is_dense_zone = (int(abs(latitude * 100) + abs(longitude * 100)) % 2 == 0) if (latitude and longitude) else False
        area_surge_fee = Decimal('25.00') if is_dense_zone else Decimal('20.00')
        surge_calculated_min = category.base_price + demand_mult_amount + area_surge_fee

        raw_price = request.POST.get('estimated_price')
        try:
            estimated_price = Decimal(str(raw_price)) if raw_price else surge_calculated_min
            if estimated_price < category.base_price:
                estimated_price = surge_calculated_min
        except (InvalidOperation, TypeError, ValueError):
            estimated_price = surge_calculated_min

        booking = Booking.objects.create(
            customer=request.user,
            service_category=category,
            description=description,
            scheduled_datetime=scheduled_datetime,
            is_emergency=is_emergency,
            address_text=address_text,
            latitude=latitude,
            longitude=longitude,
            estimated_price=estimated_price,
            status='pending'
        )

        # Log initial status
        BookingStatusHistory.objects.create(
            booking=booking,
            status='pending',
            changed_by=request.user,
            notes='Booking created'
        )

        # Matching is triggered automatically by the post_save signal (broadcasts to all nearby qualified workers)
        if is_emergency:
            messages.success(
                request,
                f'🚨 Emergency booking #{booking.pk} created! Flash broadcast sent to all verified nearby Saarthis.'
            )
        else:
            messages.success(
                request,
                f'Booking #{booking.pk} created! Broadcast sent to verified nearby Saarthis.'
            )

        return redirect('bookings:detail', pk=booking.pk)

    selected_category_id = request.GET.get('category') or request.GET.get('cat') or ''
    initial_desc = request.GET.get('desc') or request.GET.get('service') or ''

    context = {
        'categories': categories,
        'selected_category_id': selected_category_id,
        'initial_desc': initial_desc,
        'is_emergency': False,
    }
    return render(request, 'bookings/booking_create.html', context)


@login_required
def booking_detail(request, pk):
    """View booking details with matching info."""
    booking = get_object_or_404(
        Booking.objects.select_related('customer', 'worker', 'service_category'),
        pk=pk
    )

    # Access control
    if request.user not in (booking.customer, booking.worker) and \
       request.user.role not in ('coop_admin', 'platform_admin'):
        messages.error(request, 'You do not have access to this booking.')
        return redirect('bookings:list')

    status_history = booking.status_history.select_related('changed_by').all()
    has_reviewed = hasattr(booking, 'review')

    # Get matching stats if booking is still pending
    matching_stats = None
    if booking.status == 'pending' and request.user.role in ('customer', 'coop_admin', 'platform_admin'):
        matching_stats = get_matching_stats(booking)

    # Calculate time remaining for accept (for matched bookings)
    accept_time_remaining = None
    if booking.status == 'matched' and booking.matched_at:
        from core.services.matching import get_accept_timeout
        timeout = get_accept_timeout(booking)
        deadline = booking.matched_at + timezone.timedelta(seconds=timeout)
        accept_time_remaining = max(0, (deadline - timezone.now()).total_seconds())

    # Get route info when worker is assigned
    route_info = None
    if (booking.worker and hasattr(booking.worker, 'worker_profile') and
            booking.latitude and booking.longitude and
            booking.worker.worker_profile.current_latitude and booking.worker.worker_profile.current_longitude):
        from core.services.geoapify import get_route
        route_info = get_route(
            booking.worker.worker_profile.current_latitude,
            booking.worker.worker_profile.current_longitude,
            booking.latitude,
            booking.longitude,
        )

    context = {
        'booking': booking,
        'status_history': status_history,
        'has_reviewed': has_reviewed,
        'matching_stats': matching_stats,
        'accept_time_remaining': accept_time_remaining,
        'route_info': route_info,
    }
    return render(request, 'bookings/booking_detail.html', context)


@login_required
def booking_cancel(request, pk):
    """Cancel a booking."""
    booking = get_object_or_404(Booking, pk=pk)

    if not booking.can_be_cancelled:
        messages.error(request, 'This booking cannot be cancelled.')
        return redirect('bookings:detail', pk=pk)

    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        if request.user == booking.customer:
            booking.status = 'cancelled_by_customer'
        elif request.user == booking.worker:
            booking.status = 'cancelled_by_worker'
        else:
            messages.error(request, 'You cannot cancel this booking.')
            return redirect('bookings:detail', pk=pk)

        old_worker = booking.worker
        booking.cancelled_at = timezone.now()
        booking.cancellation_reason = reason
        booking.save()

        # Notify the other party
        if old_worker and request.user == booking.customer:
            Notification.objects.create(
                user=old_worker,
                title='Booking Cancelled',
                message=f'Booking #{booking.pk} ({booking.service_category.name}) has been cancelled by the customer.',
                notification_type='booking_cancelled',
                related_booking=booking,
            )
        elif booking.worker and request.user == booking.worker:
            Notification.objects.create(
                user=booking.customer,
                title='Booking Cancelled',
                message=f'Worker has cancelled Booking #{booking.pk}. Finding a new worker...',
                notification_type='booking_cancelled',
                related_booking=booking,
            )

        messages.success(request, 'Booking cancelled.')
        return redirect('bookings:list')

    return render(request, 'bookings/booking_cancel.html', {'booking': booking})


@login_required
def booking_update_status(request, pk):
    """Worker updates booking status (start, complete)."""
    booking = get_object_or_404(Booking, pk=pk)

    if request.user != booking.worker:
        messages.error(request, 'Only the assigned worker can update this status.')
        return redirect('bookings:detail', pk=pk)

    if request.method == 'POST':
        new_status = request.POST.get('status')
        valid_transitions = {
            'accepted': 'in_progress',
            'in_progress': 'completed',
        }

        current_next = valid_transitions.get(booking.status)
        if current_next == new_status:
            booking.status = new_status
            if new_status == 'completed':
                booking.completed_at = timezone.now()
                # Set final price from estimated if not set
                if not booking.final_price:
                    booking.final_price = booking.estimated_price
            booking.save()

            # Notify customer of status change
            Notification.objects.create(
                user=booking.customer,
                title=f'Booking {new_status.replace("_", " ").title()}',
                message=f'Booking #{booking.pk} ({booking.service_category.name}) is now {new_status.replace("_", " ")}.',
                notification_type='booking_completed' if new_status == 'completed' else 'booking_request',
                related_booking=booking,
            )

            if new_status == 'completed':
                messages.success(
                    request,
                    'Job completed! The customer will be prompted to leave a review and make payment.'
                )
            else:
                messages.success(request, f'Booking status updated to {new_status}.')
        else:
            messages.error(request, f'Cannot transition from {booking.status} to {new_status}.')

    return redirect('bookings:detail', pk=pk)


@login_required
def booking_accept(request, booking_id):
    """Worker accepts a matched or broadcast pending booking."""
    from django.db import transaction

    if request.user.role != 'worker':
        messages.error(request, 'Only workers can accept jobs.')
        return redirect('core:dashboard')

    with transaction.atomic():
        try:
            booking = Booking.objects.select_for_update().get(pk=booking_id)
        except Booking.DoesNotExist:
            messages.error(request, 'Booking not found.')
            return redirect('workers:dashboard')

        # Check if booking is still available
        if booking.status not in ('matched', 'pending'):
            messages.warning(request, f'Job #{booking.pk} has already been claimed by another Saarthi!')
            return redirect('workers:dashboard')

        if booking.status == 'matched' and booking.worker and booking.worker != request.user:
            messages.warning(request, f'Job #{booking.pk} was assigned to another Saarthi.')
            return redirect('workers:dashboard')

        booking.worker = request.user
        booking.status = 'accepted'
        booking.accepted_at = timezone.now()
        booking.save(update_fields=['worker', 'status', 'accepted_at', 'updated_at'])

        # Log status change
        BookingStatusHistory.objects.create(
            booking=booking,
            status='accepted',
            changed_by=request.user,
            notes=f"Claimed & accepted by {request.user.get_full_name()}"
        )

        # Mark notification for this worker as read
        Notification.objects.filter(
            related_booking=booking,
            user=request.user,
            is_read=False
        ).update(is_read=True)

        # Notify customer
        Notification.objects.create(
            user=booking.customer,
            title='Saarthi Confirmed & En Route!',
            message=(
                f'{request.user.get_full_name()} has accepted your '
                f'{booking.service_category.name} booking! '
                f'Scheduled for {booking.scheduled_datetime.strftime("%d %b, %I:%M %p")}.'
            ),
            notification_type='booking_accepted',
            related_booking=booking,
        )

    messages.success(request, f'✓ You have claimed Job #{booking.pk}! You are now confirmed.')
    
    referer = request.META.get('HTTP_REFERER', '')
    if 'dashboard' in referer:
        return redirect('workers:dashboard')
    return redirect('bookings:detail', pk=booking_id)


@login_required
def booking_reject(request, booking_id):
    """Worker passes on a booking — dismisses for this worker and reassigns if direct offer."""
    booking = get_object_or_404(Booking, pk=booking_id)

    if request.user.role != 'worker':
        messages.error(request, 'Only workers can pass on jobs.')
        return redirect('core:dashboard')

    if booking.status not in ('matched', 'pending'):
        messages.error(request, 'This booking cannot be passed in its current state.')
        return redirect('workers:dashboard')

    if request.method == 'POST':
        # If this was a direct matched offer
        if booking.status == 'matched' and booking.worker == request.user:
            excluded_ids = [request.user.id]
            result = reassign_to_next_worker(booking, set(excluded_ids))
            if result['success']:
                messages.info(
                    request,
                    f'Job #{booking.pk} passed. Offer re-routed to {result["worker"].get_full_name()}.'
                )
            else:
                messages.info(request, f'Job #{booking.pk} passed. Returned to open matching pool.')
        else:
            # Broadcast mode pass: record that this worker passed
            BookingStatusHistory.objects.create(
                booking=booking,
                status='pending',
                changed_by=request.user,
                notes=f"{request.user.get_full_name()} passed on offer"
            )
            Notification.objects.filter(
                related_booking=booking,
                user=request.user
            ).update(is_read=True)
            messages.info(request, f'Job #{booking.pk} passed and dismissed from your feed.')

    referer = request.META.get('HTTP_REFERER', '')
    if 'bookings/' in referer and 'dashboard' not in referer:
        return redirect('bookings:list')
    return redirect('workers:dashboard')


@login_required
def booking_match_status(request, pk):
    """AJAX endpoint to get live matching and broadcast status for a booking."""
    booking = get_object_or_404(Booking, pk=pk)

    # Access control
    if request.user not in (booking.customer, booking.worker) and \
       request.user.role not in ('coop_admin', 'platform_admin'):
        return JsonResponse({'error': 'Access denied'}, status=403)

    data = {
        'booking_id': booking.pk,
        'status': booking.status,
        'worker_name': booking.worker.get_full_name() if booking.worker else None,
        'worker_rating': float(booking.worker.worker_profile.avg_rating) if booking.worker and hasattr(booking.worker, 'worker_profile') else None,
        'matched_at': booking.matched_at.isoformat() if booking.matched_at else None,
        'accepted_at': booking.accepted_at.isoformat() if booking.accepted_at else None,
        'completed_at': booking.completed_at.isoformat() if booking.completed_at else None,
    }

    # Add accept countdown if matched
    if booking.status == 'matched' and booking.matched_at:
        from core.services.matching import get_accept_timeout
        timeout = get_accept_timeout(booking)
        deadline = booking.matched_at + timezone.timedelta(seconds=timeout)
        remaining = max(0, (deadline - timezone.now()).total_seconds())
        data['accept_timeout_seconds'] = remaining

    # Add broadcast candidate count if pending
    if booking.status == 'pending':
        from core.services.matching import find_nearby_workers
        candidates = find_nearby_workers(booking, max_results=10)
        data['broadcast_count'] = len(candidates)

    return JsonResponse(data)


@login_required
def booking_tracking(request, pk):
    """Customer-facing live tracking map for active bookings."""
    booking = get_object_or_404(
        Booking.objects.select_related('customer', 'worker', 'service_category'),
        pk=pk
    )

    # Only customer or the assigned worker can track
    if request.user not in (booking.customer, booking.worker) and \
       request.user.role not in ('coop_admin', 'platform_admin'):
        messages.error(request, 'You do not have access to this tracking.')
        return redirect('bookings:list')

    # Must be active (accepted or in_progress)
    if booking.status not in ('accepted', 'in_progress', 'matched'):
        messages.info(request, 'Tracking is only available for active bookings.')
        return redirect('bookings:detail', pk=pk)

    # Get worker location and route
    worker_lat = worker_lng = None
    route_info = None
    if booking.worker and hasattr(booking.worker, 'worker_profile'):
        wp = booking.worker.worker_profile
        worker_lat = wp.current_latitude
        worker_lng = wp.current_longitude

        if worker_lat and worker_lng and booking.latitude and booking.longitude:
            from core.services.geoapify import get_route
            route_info = get_route(worker_lat, worker_lng, booking.latitude, booking.longitude)

    from django.conf import settings
    context = {
        'booking': booking,
        'worker_lat': worker_lat or 28.6139,
        'worker_lng': worker_lng or 77.2090,
        'customer_lat': booking.latitude,
        'customer_lng': booking.longitude,
        'route_info': route_info,
        'geoapify_key': getattr(settings, 'GEOAPIFY_API_KEY', ''),
    }
    return render(request, 'bookings/tracking.html', context)


@login_required
def worker_location_api(request, pk):
    """AJAX endpoint — returns worker's current location for live tracking."""
    booking = get_object_or_404(Booking, pk=pk)

    if request.user not in (booking.customer, booking.worker) and \
       request.user.role not in ('coop_admin', 'platform_admin'):
        return JsonResponse({'error': 'Access denied'}, status=403)

    data = {
        'booking_id': booking.pk,
        'status': booking.status,
        'worker_name': booking.worker.get_full_name() if booking.worker else None,
    }

    if booking.worker and hasattr(booking.worker, 'worker_profile'):
        wp = booking.worker.worker_profile
        data['worker_lat'] = wp.current_latitude
        data['worker_lng'] = wp.current_longitude

    # Recalculate ETA if both locations exist
    if data.get('worker_lat') and booking.latitude:
        from core.services.geoapify import get_route
        route = get_route(
            data['worker_lat'], data['worker_lng'],
            booking.latitude, booking.longitude,
        )
        data['distance_km'] = route['distance_km']
        data['eta_min'] = route['duration_min']
        data['polyline'] = route['polyline']

    return JsonResponse(data)
