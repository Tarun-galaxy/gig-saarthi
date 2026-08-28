"""Customers web views — Dashboard, profile, onboarding."""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import CustomerProfile, SavedLocation


@login_required
def customer_dashboard(request):
    """Customer's personal dashboard with booking history."""
    if request.user.role != 'customer':
        messages.warning(request, 'This page is for customers only.')
        return redirect('core:dashboard')

    profile, _ = CustomerProfile.objects.get_or_create(user=request.user)

    active_bookings = request.user.customer_bookings.exclude(
        status__in=['completed', 'cancelled_by_customer', 'cancelled_by_worker']
    ).select_related('worker', 'service_category')

    completed_bookings = request.user.customer_bookings.filter(
        status='completed'
    ).select_related('worker', 'service_category')[:5]

    from bookings.models import ServiceCategory
    categories = ServiceCategory.objects.filter(is_active=True).order_by('name')

    cat_map = {c.name.lower(): c for c in categories}
    
    def find_cat(*keywords):
        for kw in keywords:
            for name, cat in cat_map.items():
                if kw.lower() in name:
                    return cat
        return categories.first() if categories.exists() else None

    plumbing_cat = find_cat('plumb')
    electrical_cat = find_cat('elect')
    cleaning_cat = find_cat('clean')
    carpentry_cat = find_cat('carpent', 'wood')
    cooking_cat = find_cat('cook', 'tiffin')
    painting_cat = find_cat('paint')

    popular_services = [
        {
            'name': 'Tap & Leakage Repair',
            'category': plumbing_cat,
            'icon': '🚰',
            'desc': 'Fix leaky faucets, flush valves, and pipeline fittings',
            'price': plumbing_cat.base_price if plumbing_cat else 299,
            'tag': 'Most Booked',
            'default_desc': 'Need repair for leaking tap and water pipe fittings.',
        },
        {
            'name': 'Switchboard & Socket Repair',
            'category': electrical_cat,
            'icon': '🔌',
            'desc': 'Fix short circuits, replace switchboards & wall sockets',
            'price': electrical_cat.base_price if electrical_cat else 349,
            'tag': 'Quick 30m',
            'default_desc': 'Need repair for electrical switchboard, socket, and wiring check.',
        },
        {
            'name': 'Drainage & Pipe Cleaning',
            'category': plumbing_cat,
            'icon': '🚿',
            'desc': 'Clear clogged kitchen sinks, floor traps & drain lines',
            'price': (plumbing_cat.base_price if plumbing_cat else 299) + 50,
            'tag': 'Urgent Help',
            'default_desc': 'Drainage line and sink pipe unclogging required.',
        },
        {
            'name': 'Fan & Appliance Troubleshooting',
            'category': electrical_cat,
            'icon': '🌀',
            'desc': 'Ceiling fan capacitor, regulator, & home appliance fix',
            'price': electrical_cat.base_price if electrical_cat else 349,
            'tag': 'Popular',
            'default_desc': 'Ceiling fan / appliance inspection and repair needed.',
        },
        {
            'name': 'Deep Kitchen & Bathroom Scrub',
            'category': cleaning_cat,
            'icon': '✨',
            'desc': 'Intensive tile scrubbing, oil degreasing & disinfection',
            'price': cleaning_cat.base_price if cleaning_cat else 399,
            'tag': 'Top Rated',
            'default_desc': 'Deep cleaning and sanitization for kitchen and bathroom.',
        },
        {
            'name': 'Door Lock & Furniture Fix',
            'category': carpentry_cat,
            'icon': '🚪',
            'desc': 'Lock replacement, door alignment & wooden furniture fixes',
            'price': carpentry_cat.base_price if carpentry_cat else 449,
            'tag': 'Essential',
            'default_desc': 'Door lock replacement and wooden furniture repair.',
        },
        {
            'name': 'Daily Home Cook & Tiffin',
            'category': cooking_cat,
            'icon': '🍲',
            'desc': 'Fresh homestyle breakfast, lunch, or dinner cooking',
            'price': cooking_cat.base_price if cooking_cat else 599,
            'tag': 'Daily Need',
            'default_desc': 'Home cooking service for healthy daily meals.',
        },
        {
            'name': 'Wall Touch-Up & Patch Painting',
            'category': painting_cat,
            'icon': '🖌️',
            'desc': 'Dampness treatment, plaster patch cover & wall touch-up',
            'price': painting_cat.base_price if painting_cat else 499,
            'tag': 'Expert Finish',
            'default_desc': 'Wall putty patch touch-up and paint repair.',
        },
    ]

    context = {
        'profile': profile,
        'active_bookings': active_bookings,
        'completed_bookings': completed_bookings,
        'categories': categories,
        'popular_services': popular_services,
    }
    return render(request, 'customers/dashboard.html', context)


@login_required
def customer_profile(request):
    """Customer profile page."""
    profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
    saved_locations = profile.saved_locations.all()
    return render(request, 'customers/profile.html', {
        'profile': profile,
        'saved_locations': saved_locations,
    })


@login_required
def customer_onboarding(request):
    """
    Customer onboarding — set default address with map picker.
    Includes reverse geocoding via Nominatim (free).
    """
    profile, _ = CustomerProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        profile.default_address = request.POST.get('default_address', '')
        profile.default_latitude = float(request.POST.get('latitude', 0))
        profile.default_longitude = float(request.POST.get('longitude', 0))
        profile.save()
        messages.success(request, 'Profile setup complete! You can now book services.')
        return redirect('core:dashboard')

    return render(request, 'customers/onboarding.html', {'profile': profile})


@login_required
def saved_locations(request):
    """Manage saved locations."""
    profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
    locations = profile.saved_locations.all()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add':
            label = request.POST.get('label', '').strip()
            address = request.POST.get('address', '').strip()
            latitude = float(request.POST.get('latitude', 0))
            longitude = float(request.POST.get('longitude', 0))
            is_default = request.POST.get('is_default') == 'on'

            if label and address:
                if is_default:
                    SavedLocation.objects.filter(customer=profile).update(is_default=False)
                SavedLocation.objects.create(
                    customer=profile,
                    label=label,
                    address=address,
                    latitude=latitude,
                    longitude=longitude,
                    is_default=is_default,
                )
                messages.success(request, f'Location "{label}" saved!')
            else:
                messages.error(request, 'Label and address are required.')

        elif action == 'delete':
            location_id = request.POST.get('location_id')
            SavedLocation.objects.filter(id=location_id, customer=profile).delete()
            messages.success(request, 'Location deleted.')

        elif action == 'set_default':
            location_id = request.POST.get('location_id')
            SavedLocation.objects.filter(customer=profile).update(is_default=False)
            SavedLocation.objects.filter(id=location_id, customer=profile).update(is_default=True)
            messages.success(request, 'Default location updated.')

    return redirect('accounts:profile')
