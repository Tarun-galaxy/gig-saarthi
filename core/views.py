"""Core views — Homepage, dashboard, language switcher, and shared views."""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import translation
from django.http import HttpResponseRedirect
from django.urls import resolve, reverse


def home(request):
    """Landing page — redirect to appropriate dashboard if authenticated."""
    if request.user.is_authenticated:
        if request.user.role in ('coop_admin', 'platform_admin'):
            return redirect('cooperative_admin:dashboard')
        return redirect('core:dashboard')
    
    from bookings.models import ServiceCategory
    try:
        categories = list(ServiceCategory.objects.filter(is_active=True).order_by('name'))
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Failed to fetch service categories on home page: %s", e)
        categories = []
    return render(request, 'core/home.html', {'categories': categories})


@login_required
def dashboard(request):
    """Role-based dashboard routing."""
    user = request.user
    if user.role == 'worker':
        return redirect('workers:dashboard')
    elif user.role == 'customer':
        return redirect('customers:dashboard')
    elif user.role in ('coop_admin', 'platform_admin'):
        return redirect('cooperative_admin:dashboard')
    return render(request, 'core/dashboard.html')


def set_language(request):
    """
    Language switcher view.
    Sets the language for the current session and redirects back.
    """
    if request.method == 'POST':
        language = request.POST.get('language', 'en')

        # Validate language choice
        valid_languages = [lang[0] for lang in settings.LANGUAGES]
        if language not in valid_languages:
            language = 'en'

        # Activate the language for this request
        translation.activate(language)

        # Store in session
        request.session[translation.LANGUAGE_SESSION_KEY] = language

        # Update user's preferred language if authenticated
        if request.user.is_authenticated:
            request.user.preferred_language = language
            request.user.save(update_fields=['preferred_language'])

        # Redirect back to referrer or home
        response = HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
        response.set_cookie(
            translation.LANGUAGE_COOKIE_NAME,
            language,
            max_age=365 * 24 * 60 * 60,  # 1 year
        )
        return response

    return redirect('core:home')


def custom_404(request, exception):
    """Custom 404 page."""
    return render(request, 'core/404.html', status=404)


def custom_500(request):
    """Custom 500 page."""
    return render(request, 'core/500.html', status=500)


def health_check(request):
    """
    Lightweight health check endpoint for UptimeRobot, Render, and cloud monitors.
    Returns HTTP 200 with JSON status to keep the free Render service awake.
    """
    from django.http import JsonResponse
    from django.db import connection
    db_ok = True
    try:
        connection.ensure_connection()
    except Exception:
        db_ok = False

    return JsonResponse({
        'status': 'healthy' if db_ok else 'degraded',
        'app': 'Gig Saarthi',
        'database': 'connected' if db_ok else 'unreachable',
    }, status=200 if db_ok else 503)


# Need to import settings for LANGUAGES
from django.conf import settings


def support(request):
    """
    Complaint, Support & Grievance Redressal view.
    Allows workers and customers to file complaints/disputes and view
    cooperative contact officers & emergency numbers.
    """
    from django.contrib import messages
    import random
    from notifications.models import Notification

    ticket_submitted = None
    ticket_id = None

    worker_profile = None
    if request.user.is_authenticated and hasattr(request.user, 'worker_profile'):
        worker_profile = request.user.worker_profile

    # Recent bookings for quick linkage in dispute form
    recent_bookings = []
    if request.user.is_authenticated:
        from bookings.models import Booking
        if getattr(request.user, 'role', '') == 'worker':
            recent_bookings = Booking.objects.filter(worker=request.user).select_related('service_category').order_by('-created_at')[:8]
        else:
            recent_bookings = Booking.objects.filter(customer=request.user).select_related('service_category').order_by('-created_at')[:8]

    if request.method == 'POST':
        category = request.POST.get('category', 'other')
        subject = request.POST.get('subject', '').strip()
        description = request.POST.get('description', '').strip()
        priority = request.POST.get('priority', 'normal')
        booking_id = request.POST.get('booking_id')
        contact_phone = request.POST.get('phone', '')

        if not subject or not description:
            messages.error(request, 'Please provide both a subject and details for your complaint.')
        else:
            ticket_id = f"GS-GRV-{random.randint(10000, 99999)}"
            ticket_submitted = {
                'id': ticket_id,
                'category': category,
                'subject': subject,
                'priority': priority,
            }

            # Create in-app notification if user is logged in
            if request.user.is_authenticated:
                rel_booking = None
                if booking_id:
                    from bookings.models import Booking
                    rel_booking = Booking.objects.filter(pk=booking_id).first()

                Notification.objects.create(
                    user=request.user,
                    title=f"Grievance Ticket #{ticket_id} Logged",
                    message=(
                        f"Your complaint regarding '{subject}' ({category.replace('_', ' ').title()}) "
                        f"has been submitted under ticket #{ticket_id}. "
                        "Our Cooperative Grievance Officer will review this within 24 hours."
                    ),
                    notification_type='system',
                    related_booking=rel_booking,
                )

            messages.success(
                request,
                f"Complaint registered successfully! Reference Ticket: #{ticket_id}. "
                "Our cooperative grievance team will review and contact you within 24 hours."
            )

    selected_category = request.GET.get('category', '')

    context = {
        'worker_profile': worker_profile,
        'recent_bookings': recent_bookings,
        'ticket_submitted': ticket_submitted,
        'ticket_id': ticket_id,
        'selected_category': selected_category,
    }
    return render(request, 'core/support.html', context)

