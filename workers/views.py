"""Workers web views — List, detail, dashboard, enhanced onboarding."""

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import WorkerProfile, Skill, SkillCategory
from cooperative_admin.models import Cooperative
from core.services.validation import validate_file_upload


from django.core.paginator import Paginator
from django.db.models import Count, Q


def is_coop_admin(user):
    """Check if user is a cooperative or platform admin."""
    return getattr(user, 'role', '') in ('coop_admin', 'platform_admin') or getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False)


@login_required
def worker_list(request):
    """Admin-only worker listing page divided into categories with pagination and full details."""
    if not is_coop_admin(request.user):
        messages.error(request, 'Access restricted. Only cooperative admins can view the Saarthis directory.')
        return redirect('core:dashboard')

    all_verified_workers = WorkerProfile.objects.filter(
        user__is_active=True,
        is_verified=True
    ).select_related('user', 'cooperative').prefetch_related('skills', 'skills__category')

    # Fetch all categories and annotate worker count
    # Multi-skilled workers count in each category they possess skills for!
    categories = list(SkillCategory.objects.all())
    for cat in categories:
        cat.worker_count = all_verified_workers.filter(skills__category=cat).distinct().count()

    total_all_workers = all_verified_workers.count()
    workers = all_verified_workers

    # Category filter (e.g. Plumbing, Electrical, Carpentry, Cleaning)
    selected_category = request.GET.get('category', '').strip()
    if selected_category and selected_category != 'all':
        workers = workers.filter(
            Q(skills__category__name__iexact=selected_category) |
            Q(skills__category__id__iexact=selected_category if selected_category.isdigit() else -1)
        ).distinct()

    # Skill filter
    selected_skill = request.GET.get('skill', '').strip()
    if selected_skill:
        workers = workers.filter(skills__name__iexact=selected_skill).distinct()

    # Availability filter
    availability = request.GET.get('availability', '').strip()
    if availability in ('available', 'busy', 'offline'):
        workers = workers.filter(availability_status=availability)

    # Search filter (name, phone, skills, cooperative, bio)
    search_query = request.GET.get('search', '').strip()
    if search_query:
        workers = workers.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(user__phone_number__icontains=search_query) |
            Q(skills__name__icontains=search_query) |
            Q(cooperative__name__icontains=search_query) |
            Q(bio__icontains=search_query)
        ).distinct()

    # Sort
    sort_by = request.GET.get('sort', '-avg_rating')
    if sort_by in ('-avg_rating', 'avg_rating', '-total_jobs_completed', '-created_at'):
        workers = workers.order_by(sort_by)
    else:
        workers = workers.order_by('-avg_rating', '-total_jobs_completed')

    # Pagination (9 workers per page)
    paginator = Paginator(workers, 9)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'workers': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'categories': categories,
        'total_all_workers': total_all_workers,
        'selected_category': selected_category,
        'selected_skill': selected_skill,
        'availability': availability,
        'search_query': search_query,
        'sort_by': sort_by,
    }
    return render(request, 'workers/worker_list.html', context)


def worker_detail(request, pk):
    """Worker detail page — shows all personal, KYC, skills, IDs submitted, insurance, and booking details for Admins."""
    from bookings.models import Booking
    from workers.models import WorkerInsurance

    worker = get_object_or_404(
        WorkerProfile.objects.select_related('user', 'cooperative').prefetch_related('skills', 'skills__category'),
        pk=pk,
        user__is_active=True
    )
    certifications = worker.certifications.select_related('skill').all()
    reviews = worker.user.reviews_received.select_related('customer')[:20]

    is_admin = request.user.is_authenticated and (is_coop_admin(request.user) or request.user == worker.user)

    # If admin or worker self, fetch bookings and insurance records
    bookings = []
    insurance_policies = []
    completed_bookings_count = 0
    total_revenue = 0

    if is_admin:
        bookings = Booking.objects.filter(worker=worker.user).select_related('customer', 'service').order_by('-created_at')
        insurance_policies = WorkerInsurance.objects.filter(worker=worker).order_by('-valid_till')
        completed_bookings = bookings.filter(status='completed')
        completed_bookings_count = completed_bookings.count()
        total_revenue = sum(float(b.final_price or b.estimated_price or 0) for b in completed_bookings)

    # Calculate age if DOB exists
    age = None
    if worker.user.date_of_birth:
        from django.utils import timezone
        today = timezone.now().date()
        dob = worker.user.date_of_birth
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    context = {
        'worker': worker,
        'certifications': certifications,
        'reviews': reviews,
        'bookings': bookings,
        'insurance_policies': insurance_policies,
        'completed_bookings_count': completed_bookings_count,
        'total_revenue': total_revenue,
        'age': age,
        'is_admin': is_admin,
    }
    return render(request, 'workers/worker_detail.html', context)



@login_required
def worker_dashboard(request):
    """Worker's personal dashboard — Ola/Urban Company job feed style."""
    from bookings.models import Booking
    from django.utils import timezone
    from core.services.geoapify import get_route

    if request.user.role != 'worker':
        messages.warning(request, 'This page is for workers only.')
        return redirect('core:dashboard')

    try:
        profile = request.user.worker_profile
    except WorkerProfile.DoesNotExist:
        messages.info(request, 'Please complete your worker profile first.')
        return redirect('workers:onboarding')

    from bookings.models import Booking, BookingStatusHistory
    from core.services.matching import haversine_distance, MAX_SEARCH_RADIUS_KM, EMERGENCY_SEARCH_RADIUS_KM, get_accept_timeout

    # Find IDs of bookings this worker has passed on
    passed_booking_ids = BookingStatusHistory.objects.filter(
        changed_by=request.user,
        notes__icontains='passed'
    ).values_list('booking_id', flat=True)

    # 1. Direct matched bookings
    direct_bookings = list(Booking.objects.filter(
        worker=request.user,
        status='matched',
    ).exclude(id__in=passed_booking_ids).select_related('customer', 'service_category'))

    # 2. Broadcast pending bookings matching worker's skills within search radius
    broadcast_bookings = []
    worker_skills = profile.skills.all()
    if worker_skills.exists():
        pending_candidates = Booking.objects.filter(
            status='pending',
            worker__isnull=True,
            service_category__related_skills__in=worker_skills,
        ).exclude(
            id__in=passed_booking_ids
        ).select_related('customer', 'service_category').distinct().order_by('-created_at')[:15]

        for pb in pending_candidates:
            if profile.current_latitude and profile.current_longitude and pb.latitude and pb.longitude:
                dist = haversine_distance(
                    pb.latitude, pb.longitude,
                    profile.current_latitude, profile.current_longitude
                )
                max_rad = EMERGENCY_SEARCH_RADIUS_KM if pb.is_emergency else MAX_SEARCH_RADIUS_KM
                if dist <= max_rad:
                    broadcast_bookings.append(pb)
            else:
                broadcast_bookings.append(pb)

    # Enrich direct incoming bookings with route distance + deadline
    available_with_route = []
    for booking in direct_bookings:
        route = None
        if (profile.current_latitude and profile.current_longitude and
                booking.latitude and booking.longitude):
            route = get_route(
                profile.current_latitude, profile.current_longitude,
                booking.latitude, booking.longitude,
            )
        accept_seconds = 0
        if booking.matched_at:
            timeout = get_accept_timeout(booking)
            deadline = booking.matched_at + timezone.timedelta(seconds=timeout)
            accept_seconds = max(0, (deadline - timezone.now()).total_seconds())
        available_with_route.append({
            'booking': booking,
            'route': route,
            'is_broadcast': False,
            'accept_seconds': accept_seconds,
            'accept_timeout': get_accept_timeout(booking),
        })

    # Enrich open pool broadcast gigs
    open_pool_gigs = []
    for booking in broadcast_bookings:
        route = None
        if (profile.current_latitude and profile.current_longitude and
                booking.latitude and booking.longitude):
            route = get_route(
                profile.current_latitude, profile.current_longitude,
                booking.latitude, booking.longitude,
            )
        open_pool_gigs.append({
            'booking': booking,
            'route': route,
            'is_broadcast': True,
        })

    # Active jobs (accepted / in_progress)
    active_bookings_qs = Booking.objects.filter(
        worker=request.user,
        status__in=['accepted', 'in_progress'],
    ).select_related('customer', 'service_category').order_by('scheduled_datetime')

    # Recent completed jobs
    completed_bookings = Booking.objects.filter(
        worker=request.user,
        status='completed',
    ).select_related('customer', 'service_category').order_by('-completed_at')[:5]

    # Stats
    from django.db.models import Avg, Count, Sum
    from ratings.models import Review
    total_completed = request.user.worker_bookings.filter(status='completed').count()
    avg_rating = Review.objects.filter(worker=request.user).aggregate(avg=Avg('overall_rating'))['avg'] or 0
    total_earnings = request.user.worker_bookings.filter(
        status='completed'
    ).aggregate(total=Sum('final_price'))['total'] or 0

    # Enrich active bookings with route to customer
    active_with_route = []
    for booking in active_bookings_qs:
        route = None
        if (profile.current_latitude and profile.current_longitude and
                booking.latitude and booking.longitude):
            route = get_route(
                profile.current_latitude, profile.current_longitude,
                booking.latitude, booking.longitude,
            )
        active_with_route.append({
            'booking': booking,
            'route': route,
        })

    context = {
        'profile': profile,
        'available_jobs': available_with_route,
        'open_pool_gigs': open_pool_gigs,
        'active_bookings': active_with_route,
        'completed_bookings': completed_bookings,
        'total_completed': total_completed,
        'avg_rating': avg_rating,
        'total_earnings': total_earnings,
        'worker_lat': profile.current_latitude,
        'worker_lng': profile.current_longitude,
    }
    return render(request, 'workers/dashboard.html', context)


@login_required
def worker_onboarding(request):
    """
    Multi-step worker onboarding with session-based wizard.
    
    Steps:
    1. Basic details (name, bio, experience, location)
    2. Skill selection
    3. Document upload (ID proof, certificates)
    4. Cooperative assignment
    5. Bank details for payouts
    """
    if request.user.role != 'worker':
        return redirect('core:dashboard')

    profile, created = WorkerProfile.objects.get_or_create(user=request.user)
    categories = SkillCategory.objects.prefetch_related('skills').all()
    cooperatives = Cooperative.objects.filter(is_active=True)

    # Get current step from session or default to 1
    step = request.session.get('onboarding_step', '1')
    if request.GET.get('step'):
        step = request.GET['step']
        request.session['onboarding_step'] = step

    if request.method == 'POST':
        action = request.POST.get('action', 'next')

        if action == 'back':
            # Go to previous step
            step_num = int(step)
            if step_num > 1:
                step = str(step_num - 1)
                request.session['onboarding_step'] = step
                return redirect(f'{request.path}?step={step}')

        elif step == '1':
            # Basic details
            request.user.first_name = request.POST.get('first_name', request.user.first_name)
            request.user.last_name = request.POST.get('last_name', request.user.last_name)
            request.user.save()
            profile.bio = request.POST.get('bio', '')
            experience = request.POST.get('experience_years', 0)
            try:
                profile.experience_years = int(experience)
            except (ValueError, TypeError):
                pass
            profile.current_latitude = float(request.POST.get('latitude', profile.current_latitude))
            profile.current_longitude = float(request.POST.get('longitude', profile.current_longitude))
            profile.save()
            messages.success(request, 'Step 1 complete! Now select your skills.')
            step = '2'
            request.session['onboarding_step'] = step

        elif step == '2':
            # Skill selection
            skill_ids = request.POST.getlist('skills')
            profile.skills.set(Skill.objects.filter(id__in=skill_ids))
            messages.success(request, f'Skills saved! ({len(skill_ids)} skills selected)')
            step = '3'
            request.session['onboarding_step'] = step

        elif step == '3':
            # Document upload with validation
            profile.id_proof_type = request.POST.get('id_proof_type', '')
            if 'id_proof_file' in request.FILES:
                uploaded_file = request.FILES['id_proof_file']
                is_valid, error = validate_file_upload(uploaded_file, 'id_proof')
                if not is_valid:
                    messages.error(request, f'Document upload failed: {error}')
                    return redirect(f'{request.path}?step=3')
                profile.id_proof_file = uploaded_file
            profile.save()
            messages.success(request, 'Documents uploaded! Select your cooperative.')
            step = '4'
            request.session['onboarding_step'] = step

        elif step == '4':
            # Cooperative assignment
            coop_id = request.POST.get('cooperative')
            if coop_id:
                try:
                    profile.cooperative = Cooperative.objects.get(id=coop_id)
                except Cooperative.DoesNotExist:
                    pass
            profile.save()
            messages.success(request, 'Cooperative selected! Add bank details.')
            step = '5'
            request.session['onboarding_step'] = step

        elif step == '5':
            # Bank details
            profile.bank_account_number = request.POST.get('bank_account_number', '')
            profile.bank_ifsc_code = request.POST.get('bank_ifsc_code', '')
            profile.bank_name = request.POST.get('bank_name', '')
            profile.upi_id = request.POST.get('upi_id', '')
            profile.availability_status = 'available'
            profile.save()

            # Clean up session
            if 'onboarding_step' in request.session:
                del request.session['onboarding_step']

            messages.success(
                request,
                'Profile submitted! A cooperative admin will verify your application. '
                'You can start receiving bookings once verified.'
            )
            return redirect('core:dashboard')

        return redirect(f'{request.path}?step={step}')

    return render(request, 'workers/onboarding.html', {
        'step': step,
        'profile': profile,
        'categories': categories,
        'cooperatives': cooperatives,
        'total_steps': 5,
    })


@login_required
def my_profile(request):
    """Worker's own profile page — redirects to unified accounts:profile."""
    return redirect('accounts:profile')



from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
@login_required
def worker_ai_chat_api(request):
    """API endpoint for worker AI chatbot (Saarthi Sahayak)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    try:
        import json
        from .services.ai_assistant import process_worker_chat
        
        data = json.loads(request.body.decode('utf-8'))
        message = data.get('message', '').strip()
        history = data.get('history', [])
        
        if not message:
            return JsonResponse({'error': 'Message cannot be empty'}, status=400)

        result = process_worker_chat(message, request.user, history)
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({'error': str(e), 'status': 'error'}, status=500)


@csrf_exempt
@login_required
def worker_update_location(request):
    """API endpoint to update worker's live GPS coordinates and recalculate active route."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    try:
        import json
        data = json.loads(request.body.decode('utf-8'))
        lat = float(data.get('latitude'))
        lng = float(data.get('longitude'))
        booking_id = data.get('booking_id')
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({'error': 'Invalid coordinates'}, status=400)

    if hasattr(request.user, 'worker_profile'):
        wp = request.user.worker_profile
        wp.current_latitude = lat
        wp.current_longitude = lng
        wp.save(update_fields=['current_latitude', 'current_longitude'])

        route_info = None
        if booking_id:
            from bookings.models import Booking
            booking = Booking.objects.filter(pk=booking_id, worker=request.user).first()
            if booking and booking.latitude and booking.longitude:
                from core.services.geoapify import get_route
                route_info = get_route(lat, lng, booking.latitude, booking.longitude)

        return JsonResponse({
            'status': 'ok',
            'latitude': lat,
            'longitude': lng,
            'route': route_info,
        })
    return JsonResponse({'error': 'Worker profile not found'}, status=404)


@login_required
def worker_earnings(request):
    """
    Worker Earnings & Monthly Income Dashboard.
    Provides full monthly breakdown, cooperative fee deduction (5%),
    and payout ledger.
    """
    if request.user.role != 'worker':
        messages.info(request, 'Earnings overview is available for registered Saarthis.')
        return redirect('core:dashboard')

    try:
        profile = request.user.worker_profile
    except WorkerProfile.DoesNotExist:
        return redirect('workers:onboarding')

    from bookings.models import Booking
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Sum, Count, Q

    now = timezone.now()
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 1. This Month Stats
    this_month_bookings = Booking.objects.filter(
        worker=request.user,
        status='completed',
    ).filter(
        Q(completed_at__gte=this_month_start) | Q(completed_at__isnull=True, created_at__gte=this_month_start)
    )
    this_month_jobs_count = this_month_bookings.count()
    this_month_gross = float(this_month_bookings.aggregate(s=Sum('final_price'))['s'] or 0)
    if this_month_gross == 0 and this_month_jobs_count > 0:
        this_month_gross = float(this_month_bookings.aggregate(s=Sum('estimated_price'))['s'] or 0)

    coop_fee_rate = 0.05
    this_month_coop_fee = round(this_month_gross * coop_fee_rate, 2)
    this_month_net = round(this_month_gross - this_month_coop_fee, 2)

    # 2. Previous Month Stats (for comparison)
    last_month_end = this_month_start - timedelta(seconds=1)
    last_month_start = last_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_bookings = Booking.objects.filter(
        worker=request.user,
        status='completed',
    ).filter(
        Q(completed_at__range=(last_month_start, last_month_end)) | 
        Q(completed_at__isnull=True, created_at__range=(last_month_start, last_month_end))
    )
    last_month_gross = float(last_month_bookings.aggregate(s=Sum('final_price'))['s'] or 0)
    if last_month_gross == 0 and last_month_bookings.count() > 0:
        last_month_gross = float(last_month_bookings.aggregate(s=Sum('estimated_price'))['s'] or 0)
    last_month_net = round(last_month_gross * 0.95, 2)

    # Growth %
    growth_pct = None
    if last_month_net > 0:
        growth_pct = round(((this_month_net - last_month_net) / last_month_net) * 100, 1)

    # 3. Lifetime Stats
    all_completed = Booking.objects.filter(
        worker=request.user,
        status='completed',
    ).select_related('customer', 'service_category').order_by('-completed_at', '-created_at')

    lifetime_jobs_count = all_completed.count()
    lifetime_gross = float(all_completed.aggregate(s=Sum('final_price'))['s'] or 0)
    if lifetime_gross == 0 and lifetime_jobs_count > 0:
        lifetime_gross = float(all_completed.aggregate(s=Sum('estimated_price'))['s'] or 0)
    lifetime_coop_fee = round(lifetime_gross * coop_fee_rate, 2)
    lifetime_net = round(lifetime_gross - lifetime_coop_fee, 2)

    # 4. Past 6 Months Breakdown
    monthly_breakdown = []
    curr = this_month_start
    for i in range(6):
        m_start = curr
        if curr.month == 12:
            m_next = curr.replace(year=curr.year + 1, month=1)
        else:
            m_next = curr.replace(month=curr.month + 1)
        m_end = m_next - timedelta(seconds=1)

        m_b = Booking.objects.filter(
            worker=request.user,
            status='completed',
        ).filter(
            Q(completed_at__range=(m_start, m_end)) |
            Q(completed_at__isnull=True, created_at__range=(m_start, m_end))
        )
        count = m_b.count()
        gross = float(m_b.aggregate(s=Sum('final_price'))['s'] or 0)
        if gross == 0 and count > 0:
            gross = float(m_b.aggregate(s=Sum('estimated_price'))['s'] or 0)
        net = round(gross * 0.95, 2)
        fee = round(gross * 0.05, 2)

        monthly_breakdown.append({
            'month_label': m_start.strftime('%B %Y'),
            'month_short': m_start.strftime('%b %Y'),
            'jobs_count': count,
            'gross': gross,
            'coop_fee': fee,
            'net': net,
            'is_current': (i == 0),
        })

        curr = (m_start - timedelta(days=1)).replace(day=1)

    # 5. Recent Completed Bookings with payout breakdown
    recent_bookings = []
    for b in all_completed[:15]:
        b_gross = float(b.final_price or b.estimated_price or 0)
        b_fee = round(b_gross * coop_fee_rate, 2)
        b_net = round(b_gross - b_fee, 2)
        recent_bookings.append({
            'booking': b,
            'gross': b_gross,
            'fee': b_fee,
            'net': b_net,
            'date': b.completed_at or b.created_at,
        })

    # Bank account masked
    masked_account = ''
    if profile.bank_account_number:
        acc = str(profile.bank_account_number)
        masked_account = '•••• •••• ' + acc[-4:] if len(acc) >= 4 else acc

    context = {
        'profile': profile,
        'this_month_gross': this_month_gross,
        'this_month_net': this_month_net,
        'this_month_coop_fee': this_month_coop_fee,
        'this_month_jobs_count': this_month_jobs_count,
        'last_month_net': last_month_net,
        'growth_pct': growth_pct,
        'lifetime_gross': lifetime_gross,
        'lifetime_net': lifetime_net,
        'lifetime_coop_fee': lifetime_coop_fee,
        'lifetime_jobs_count': lifetime_jobs_count,
        'monthly_breakdown': monthly_breakdown,
        'recent_bookings': recent_bookings,
        'masked_account': masked_account,
        'now': now,
    }
    return render(request, 'workers/earnings.html', context)


@login_required
def apply_insurance(request):
    """Allow worker to apply for cooperative safety insurance directly from their profile."""
    if request.user.role != 'worker':
        messages.error(request, 'Only registered workers can apply for cooperative safety insurance.')
        return redirect('accounts:profile')

    if request.method == 'POST':
        coverage_type = request.POST.get('coverage_type', 'accident')
        nominee_name = request.POST.get('nominee_name', '').strip()
        nominee_relation = request.POST.get('nominee_relation', '').strip()
        nominee_phone = request.POST.get('nominee_phone', '').strip()

        coverage_amounts = {
            'accident': 500000.00,
            'health': 250000.00,
            'life': 1000000.00,
            'combined': 750000.00,
        }
        coverage_amount = coverage_amounts.get(coverage_type, 500000.00)

        import random
        from datetime import date, timedelta
        from workers.models import WorkerProfile, WorkerInsurance
        from notifications.models import Notification
        from accounts.models import User

        profile, _ = WorkerProfile.objects.get_or_create(user=request.user)

        # Generate a unique policy / application reference
        rand_suffix = random.randint(10000, 99999)
        policy_num = f"GS-INS-{request.user.id}-{rand_suffix}"

        today = date.today()
        valid_till = today + timedelta(days=365)

        insurance = WorkerInsurance.objects.create(
            worker=profile,
            policy_number=policy_num,
            provider='National Cooperative Insurance Federation (NCCT)',
            coverage_type=coverage_type,
            coverage_amount=coverage_amount,
            valid_from=today,
            valid_till=valid_till,
            status='pending',
        )

        # Notify the worker
        Notification.objects.create(
            user=request.user,
            title='Insurance Application Submitted 🛡️',
            message=(
                f"Your application for {insurance.get_coverage_type_display()} (Ref: {policy_num}) "
                f"with ₹{int(coverage_amount):,} cover has been submitted to your cooperative admin. "
                "Review & activation takes 24–48 hours."
            ),
            notification_type='insurance_update',
        )

        # Notify cooperative admins
        admins = User.objects.filter(role__in=['coop_admin', 'platform_admin'], is_active=True)
        for admin in admins:
            Notification.objects.create(
                user=admin,
                title='New Insurance Application 🛡️',
                message=(
                    f"Worker {request.user.get_full_name() or request.user.username} applied for "
                    f"{insurance.get_coverage_type_display()} (Ref: {policy_num}). Please review in Admin Console."
                ),
                notification_type='insurance_update',
            )

        messages.success(
            request,
            f"🛡️ Your insurance application for {insurance.get_coverage_type_display()} (₹{int(coverage_amount):,} cover) has been submitted successfully! Your cooperative admin will review and activate it."
        )
        return redirect('accounts:profile')

    return redirect('accounts:profile')



