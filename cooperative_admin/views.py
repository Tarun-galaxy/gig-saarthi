"""Cooperative Admin views — Enhanced dashboard with stats, charts, verification, and management."""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from django.http import JsonResponse
from bookings.models import Booking
from payments.models import Invoice, WorkerPayout
from workers.models import WorkerProfile
from ratings.models import Review
from notifications.models import Notification
from .models import Cooperative
from core.services.forecasting import get_forecast_summary


def is_coop_admin(user):
    """Check if user is a cooperative or platform admin."""
    return user.role in ('coop_admin', 'platform_admin')


@login_required
@user_passes_test(is_coop_admin)
def admin_dashboard(request):
    """Enhanced cooperative admin dashboard with comprehensive stats."""
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # ── Worker Stats ──
    total_workers = WorkerProfile.objects.count()
    verified_workers = WorkerProfile.objects.filter(is_verified=True).count()
    pending_workers = WorkerProfile.objects.filter(is_verified=False).count()
    available_workers = WorkerProfile.objects.filter(
        is_verified=True, availability_status='available'
    ).count()

    # ── Booking Stats ──
    active_bookings = Booking.objects.exclude(
        status__in=['completed', 'cancelled_by_customer', 'cancelled_by_worker']
    ).count()
    completed_bookings = Booking.objects.filter(status='completed').count()
    pending_bookings = Booking.objects.filter(status='pending').count()
    disputed_bookings = Booking.objects.filter(status='disputed').count()

    # Booking status distribution for chart
    booking_status_dist = Booking.objects.values('status').annotate(
        count=Count('id')
    ).order_by('status')

    # ── Revenue Stats ──
    monthly_revenue = Invoice.objects.filter(
        status='paid', paid_at__gte=month_start
    ).aggregate(total=Sum('amount'))['total'] or 0

    monthly_platform_fee = Invoice.objects.filter(
        status='paid', paid_at__gte=month_start
    ).aggregate(total=Sum('platform_fee'))['total'] or 0

    total_revenue = Invoice.objects.filter(
        status='paid'
    ).aggregate(total=Sum('amount'))['total'] or 0

    # ── Rating Stats ──
    avg_rating = WorkerProfile.objects.filter(
        is_verified=True, total_reviews__gt=0
    ).aggregate(avg=Avg('avg_rating'))['avg'] or 0

    flagged_reviews = Review.objects.filter(is_flagged=True).select_related(
        'customer', 'worker', 'booking'
    )[:5]

    # ── Insurance Stats ──
    from workers.models import WorkerInsurance
    active_insurance = WorkerInsurance.objects.filter(status='active').count()
    expiring_soon = WorkerInsurance.objects.filter(
        status='active',
        valid_till__lte=now + timezone.timedelta(days=30),
        valid_till__gte=now
    ).count()

    # ── Recent Activity with Pagination ──
    from django.core.paginator import Paginator
    
    booking_qs = Booking.objects.select_related(
        'customer', 'worker', 'service_category'
    ).order_by('-created_at')

    status_filter = request.GET.get('status_filter', '')
    if status_filter and status_filter != 'all':
        if status_filter == 'active':
            booking_qs = booking_qs.filter(status__in=['accepted', 'in_progress', 'matched'])
        elif status_filter == 'pending':
            booking_qs = booking_qs.filter(status='pending')
        elif status_filter == 'completed':
            booking_qs = booking_qs.filter(status='completed')
        else:
            booking_qs = booking_qs.filter(status=status_filter)

    search_q = request.GET.get('search_q', '').strip()
    if search_q:
        booking_qs = booking_qs.filter(
            Q(id__icontains=search_q) |
            Q(customer__first_name__icontains=search_q) |
            Q(customer__last_name__icontains=search_q) |
            Q(customer__username__icontains=search_q) |
            Q(worker__first_name__icontains=search_q) |
            Q(worker__last_name__icontains=search_q) |
            Q(service_category__name__icontains=search_q)
        )

    paginator = Paginator(booking_qs, 8)
    page_number = request.GET.get('page', 1)
    recent_bookings = paginator.get_page(page_number)

    recent_notifications = Notification.objects.filter(
        is_read=False
    ).select_related('user')[:5]

    # ── Cooperatives ──
    cooperatives = Cooperative.objects.annotate(
        num_workers=Count('workers'),
        num_verified=Count('workers', filter=Q(workers__is_verified=True)),
    )

    # ── Weekly Revenue Chart Data ──
    weekly_revenue = []
    for i in range(7):
        day = now - timezone.timedelta(days=6 - i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timezone.timedelta(days=1)
        revenue = Invoice.objects.filter(
            status='paid', paid_at__gte=day_start, paid_at__lt=day_end
        ).aggregate(total=Sum('amount'))['total'] or 0
        weekly_revenue.append({
            'date': day.strftime('%a'),
            'amount': float(revenue)
        })

    context = {
        # Workers
        'total_workers': total_workers,
        'verified_workers': verified_workers,
        'pending_workers': pending_workers,
        'available_workers': available_workers,
        # Bookings
        'active_bookings': active_bookings,
        'completed_bookings': completed_bookings,
        'pending_bookings': pending_bookings,
        'disputed_bookings': disputed_bookings,
        'booking_status_dist': list(booking_status_dist),
        # Revenue
        'monthly_revenue': monthly_revenue,
        'monthly_platform_fee': monthly_platform_fee,
        'total_revenue': total_revenue,
        'weekly_revenue': weekly_revenue,
        # Ratings
        'avg_rating': round(avg_rating, 2),
        'flagged_reviews': flagged_reviews,
        # Insurance
        'active_insurance': active_insurance,
        'expiring_insurance': expiring_soon,
        # Activity
        'recent_bookings': recent_bookings,
        'recent_notifications': recent_notifications,
        'status_filter': status_filter,
        'search_q': search_q,
        # Cooperatives
        'cooperatives': cooperatives,
    }

    # Demand forecast data
    try:
        forecast_summary = get_forecast_summary()
        context['forecast_summary'] = forecast_summary
        context['has_forecast_data'] = forecast_summary['total_forecasts'] > 0
    except Exception:
        context['has_forecast_data'] = False
        context['forecast_summary'] = {}

    return render(request, 'cooperative_admin/dashboard.html', context)


@login_required
@user_passes_test(is_coop_admin)
def admin_booking_monitor(request):
    """Live booking monitor with pagination and status filtering."""
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '').strip()
    
    bookings_qs = Booking.objects.select_related(
        'customer', 'worker', 'service_category'
    ).order_by('-created_at')

    if status_filter:
        bookings_qs = bookings_qs.filter(status=status_filter)

    if search_query:
        bookings_qs = bookings_qs.filter(
            Q(id__icontains=search_query) |
            Q(customer__first_name__icontains=search_query) |
            Q(customer__last_name__icontains=search_query) |
            Q(customer__username__icontains=search_query) |
            Q(worker__first_name__icontains=search_query) |
            Q(worker__last_name__icontains=search_query) |
            Q(service_category__name__icontains=search_query)
        )
    
    from django.core.paginator import Paginator
    paginator = Paginator(bookings_qs, 15)
    page_number = request.GET.get('page', 1)
    bookings = paginator.get_page(page_number)

    context = {
        'bookings': bookings,
        'status_filter': status_filter,
        'search_query': search_query,
        'status_choices': Booking.STATUS_CHOICES,
    }
    return render(request, 'cooperative_admin/booking_monitor.html', context)



@login_required
@user_passes_test(is_coop_admin)
def admin_api_stats(request):
    """AJAX endpoint for live dashboard stats (for auto-refresh)."""
    now = timezone.now()
    
    stats = {
        'total_workers': WorkerProfile.objects.count(),
        'pending_workers': WorkerProfile.objects.filter(is_verified=False).count(),
        'active_bookings': Booking.objects.exclude(
            status__in=['completed', 'cancelled_by_customer', 'cancelled_by_worker']
        ).count(),
        'pending_bookings': Booking.objects.filter(status='pending').count(),
        'disputed_bookings': Booking.objects.filter(status='disputed').count(),
        'unread_notifications': Notification.objects.filter(is_read=False).count(),
    }
    return JsonResponse(stats)


@login_required
@user_passes_test(is_coop_admin)
def worker_verification_list(request):
    """List workers pending verification with search."""
    search = request.GET.get('search', '').strip()
    
    pending_workers = WorkerProfile.objects.filter(
        is_verified=False
    ).select_related('user', 'cooperative').prefetch_related('skills')

    if search:
        pending_workers = pending_workers.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__phone_number__icontains=search)
        )

    verified_workers = WorkerProfile.objects.filter(
        is_verified=True
    ).select_related('user', 'cooperative')[:20]

    context = {
        'pending_workers': pending_workers,
        'verified_workers': verified_workers,
        'search_query': search,
    }
    return render(request, 'cooperative_admin/worker_verification.html', context)


@login_required
@user_passes_test(is_coop_admin)
def verify_worker(request, worker_id):
    """Approve and verify a worker."""
    worker = get_object_or_404(WorkerProfile, pk=worker_id)

    if request.method == 'POST':
        worker.is_verified = True
        worker.verification_date = timezone.now()
        worker.save()

        worker.certifications.update(
            is_verified=True,
            verified_by=request.user,
            verification_date=timezone.now()
        )

        Notification.objects.create(
            user=worker.user,
            title='Profile Verified!',
            message='Your profile has been verified by your cooperative. You can now receive bookings.',
            notification_type='verification_approved'
        )

        messages.success(request, f'{worker.user.get_full_name()} has been verified.')

    return redirect('cooperative_admin:worker_verification')


@login_required
@user_passes_test(is_coop_admin)
def reject_worker(request, worker_id):
    """Reject a worker's verification."""
    worker = get_object_or_404(WorkerProfile, pk=worker_id)

    if request.method == 'POST':
        reason = request.POST.get('reason', 'Verification rejected')

        Notification.objects.create(
            user=worker.user,
            title='Verification Rejected',
            message=f'Your profile verification was rejected. Reason: {reason}',
            notification_type='verification_rejected'
        )

        messages.warning(request, f'{worker.user.get_full_name()} verification rejected.')

    return redirect('cooperative_admin:worker_verification')


@login_required
@user_passes_test(is_coop_admin)
def cooperative_list(request):
    """List all cooperatives."""
    cooperatives = Cooperative.objects.annotate(
        num_workers=Count('workers'),
        num_verified=Count('workers', filter=Q(workers__is_verified=True)),
    )
    return render(request, 'cooperative_admin/cooperative_list.html', {
        'cooperatives': cooperatives
    })


@login_required
@user_passes_test(is_coop_admin)
def cooperative_detail(request, pk):
    """Cooperative detail with worker list and stats."""
    cooperative = get_object_or_404(Cooperative, pk=pk)
    workers = WorkerProfile.objects.filter(
        cooperative=cooperative
    ).select_related('user').prefetch_related('skills')

    # Cooperative stats
    total_bookings = Booking.objects.filter(
        worker__worker_profile__cooperative=cooperative
    ).count()
    
    completed_bookings = Booking.objects.filter(
        worker__worker_profile__cooperative=cooperative,
        status='completed'
    ).count()
    
    total_revenue = Invoice.objects.filter(
        booking__worker__worker_profile__cooperative=cooperative,
        status='paid'
    ).aggregate(total=Sum('amount'))['total'] or 0

    context = {
        'cooperative': cooperative,
        'workers': workers,
        'total_bookings': total_bookings,
        'completed_bookings': completed_bookings,
        'total_revenue': total_revenue,
    }
    return render(request, 'cooperative_admin/cooperative_detail.html', context)


@login_required
@user_passes_test(is_coop_admin)
def insurance_management(request):
    """Insurance & Safety Pool management panel for cooperative admins."""
    from workers.models import WorkerInsurance
    import uuid

    # All insurance policies
    all_policies = WorkerInsurance.objects.select_related(
        'worker__user', 'enrolled_by'
    ).order_by('-valid_till')

    active_policies = all_policies.filter(status='active')
    pending_policies = all_policies.filter(status='pending')
    expired_policies = all_policies.filter(status='expired')

    # Workers without active insurance
    workers_without_insurance = WorkerProfile.objects.filter(
        is_verified=True
    ).exclude(
        insurance_policies__status='active'
    ).select_related('user')

    # Safety Pool financial summary from 5% cooperative fees
    total_platform_fees = Invoice.objects.filter(
        status='paid'
    ).aggregate(total=Sum('platform_fee'))['total'] or 0

    safety_pool = {
        'total_collected': float(total_platform_fees),
        'insurance_pool': round(float(total_platform_fees) * 0.60, 2),
        'emergency_fund': round(float(total_platform_fees) * 0.25, 2),
        'reserve': round(float(total_platform_fees) * 0.15, 2),
    }

    context = {
        'all_policies': all_policies,
        'active_policies': active_policies,
        'pending_policies': pending_policies,
        'expired_policies': expired_policies,
        'workers_without_insurance': workers_without_insurance,
        'safety_pool': safety_pool,
        'total_active': active_policies.count(),
        'total_pending': pending_policies.count(),
        'total_expired': expired_policies.count(),
        'total_uninsured': workers_without_insurance.count(),
    }
    return render(request, 'cooperative_admin/insurance_management.html', context)


@login_required
@user_passes_test(is_coop_admin)
def enroll_insurance(request, worker_id):
    """Enroll a worker in the cooperative safety insurance program."""
    from workers.models import WorkerInsurance
    import uuid

    worker_profile = get_object_or_404(WorkerProfile, pk=worker_id)

    if request.method == 'POST':
        coverage_type = request.POST.get('coverage_type', 'combined')
        coverage_amount = request.POST.get('coverage_amount', '500000')

        now = timezone.now()
        policy_number = f"GS-COOP-{now.year}-{uuid.uuid4().hex[:6].upper()}"

        WorkerInsurance.objects.create(
            worker=worker_profile,
            policy_number=policy_number,
            provider='Gig Saarthi Cooperative Safety Pool',
            coverage_type=coverage_type,
            coverage_amount=coverage_amount,
            valid_from=now.date(),
            valid_till=(now + timezone.timedelta(days=365)).date(),
            status='active',
            enrolled_by=request.user,
        )

        messages.success(
            request,
            f'✅ {worker_profile.user.get_full_name()} enrolled in {coverage_type} insurance — Policy: {policy_number}'
        )

    return redirect('cooperative_admin:insurance_management')


@login_required
@user_passes_test(is_coop_admin)
def approve_insurance(request, policy_id):
    """Approve and activate a worker's pending insurance application."""
    from workers.models import WorkerInsurance
    from notifications.models import Notification
    
    policy = get_object_or_404(WorkerInsurance, pk=policy_id)
    policy.status = 'active'
    policy.enrolled_by = request.user
    policy.save()

    # Notify worker
    Notification.objects.create(
        user=policy.worker.user,
        title='Insurance Policy Activated! 🛡️',
        message=f'Congratulations! Your {policy.get_coverage_type_display()} policy ({policy.policy_number}) for ₹{int(policy.coverage_amount):,} has been approved and activated by cooperative admin.',
        notification_type='insurance_update',
    )

    messages.success(request, f'✅ Policy {policy.policy_number} for {policy.worker.user.get_full_name()} has been approved and activated.')
    return redirect('cooperative_admin:insurance_management')

