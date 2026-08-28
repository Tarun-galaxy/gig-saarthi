"""Notifications web views — List and manage notifications."""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import Notification


@login_required
def notification_list(request):
    """Render notifications page with role-distinctive filtering."""
    user = request.user
    category_filter = request.GET.get('type', 'all')
    
    qs = user.notifications.select_related('related_booking', 'related_booking__service_category')
    
    if category_filter == 'jobs':
        qs = qs.filter(notification_type__in=['booking_request', 'booking_accepted', 'booking_completed', 'booking_cancelled'])
    elif category_filter == 'payments':
        qs = qs.filter(notification_type__in=['payment_received', 'payment_failed'])
    elif category_filter == 'account':
        qs = qs.filter(notification_type__in=['verification_approved', 'verification_rejected', 'insurance_update', 'review_received', 'system'])

    notifications = qs[:60]
    unread_count = user.notifications.filter(is_read=False).count()

    context = {
        'notifications': notifications,
        'selected_category': category_filter,
        'unread_count': unread_count,
        'is_worker': user.is_worker,
        'is_customer': user.is_customer,
    }
    return render(request, 'notifications/list.html', context)


@login_required
def mark_read(request, pk):
    """Mark a single notification as read."""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save(update_fields=['is_read'])

    if request.headers.get('HX-Request'):
        return JsonResponse({'status': 'ok'})

    return redirect(request.META.get('HTTP_REFERER', 'core:dashboard'))


@login_required
def mark_all_read(request):
    """Mark all notifications as read for the current user."""
    if request.method == 'POST':
        Notification.objects.filter(
            user=request.user, is_read=False
        ).update(is_read=True)

    if request.headers.get('HX-Request'):
        return JsonResponse({'status': 'ok'})

    return redirect(request.META.get('HTTP_REFERER', 'core:dashboard'))

