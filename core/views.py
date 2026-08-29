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
    categories = ServiceCategory.objects.filter(is_active=True).order_by('name')
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
