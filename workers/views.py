"""Workers web views — List, detail, dashboard, enhanced onboarding."""

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import WorkerProfile, Skill, SkillCategory
from cooperative_admin.models import Cooperative
from core.services.validation import validate_file_upload


def is_coop_admin(user):
    """Check if user is a cooperative or platform admin."""
    return getattr(user, 'role', '') in ('coop_admin', 'platform_admin') or getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False)


@login_required
def worker_list(request):
    """Admin-only worker listing page with filters."""
    if not is_coop_admin(request.user):
        messages.error(request, 'Access restricted. Only cooperative admins can view the Saarthis directory.')
        return redirect('core:dashboard')

    workers = WorkerProfile.objects.filter(
        user__is_active=True,
        is_verified=True
    ).select_related('user', 'cooperative').prefetch_related('skills')

    # Filter by skill category
    category = request.GET.get('category')
    if category:
        workers = workers.filter(skills__category__name=category).distinct()

    # Filter by skill
    skill = request.GET.get('skill')
    if skill:
        workers = workers.filter(skills__name=skill).distinct()

    # Filter by availability
    availability = request.GET.get('availability')
    if availability:
        workers = workers.filter(availability_status=availability)

    # Search
    search = request.GET.get('search', '').strip()
    if search:
        from django.db.models import Q
        workers = workers.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(skills__name__icontains=search) |
            Q(bio__icontains=search)
        ).distinct()

    categories = SkillCategory.objects.all()

    context = {
        'workers': workers,
        'categories': categories,
        'selected_category': category,
        'selected_skill': skill,
        'search_query': search,
    }
    return render(request, 'workers/worker_list.html', context)


def worker_detail(request, pk):
    """Public worker profile page."""
    worker = get_object_or_404(
        WorkerProfile.objects.select_related('user', 'cooperative').prefetch_related('skills'),
        pk=pk,
        user__is_active=True
    )
    certifications = worker.certifications.select_related('skill').all()
    reviews = worker.user.reviews_received.select_related('customer')[:10]

    context = {
        'worker': worker,
        'certifications': certifications,
        'reviews': reviews,
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

    all_incoming_bookings = direct_bookings + broadcast_bookings

    # Enrich available incoming bookings with route distance + deadline
    available_with_route = []
    for booking in all_incoming_bookings:
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
            'is_broadcast': (booking.status == 'pending'),
            'accept_seconds': accept_seconds,
            'accept_timeout': get_accept_timeout(booking),
        })

    # Enrich active bookings with route to customer
    active_with_route = []
    for booking in active_bookings:
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
    """Worker's own profile page."""
    try:
        profile = request.user.worker_profile
    except WorkerProfile.DoesNotExist:
        return redirect('workers:onboarding')

    certifications = profile.certifications.select_related('skill').all()
    reviews = request.user.reviews_received.select_related('customer')[:10]
    insurance = profile.insurance_policies.filter(status='active')

    context = {
        'profile': profile,
        'certifications': certifications,
        'reviews': reviews,
        'insurance': insurance,
    }
    return render(request, 'workers/my_profile.html', context)


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

