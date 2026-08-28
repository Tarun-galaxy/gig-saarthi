"""Accounts web views — Registration with OTP, login, profile management."""

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate, get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from core.services.otp import (
    create_otp_verification, verify_otp,
    is_phone_verified_recently, OTP_EXPIRY_MINUTES
)
from core.services.validation import check_rate_limit, rate_limit_key, validate_file_upload

User = get_user_model()


# ── Registration Flow ──────────────────────────────────────────────

def register_step1(request):
    """
    Step 1: User fills in basic info + role selection.
    Session stores form data between steps.
    """
    if request.method == 'POST':
        # Validate basic fields
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        username = request.POST.get('username', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        email = request.POST.get('email', '').strip()
        role = request.POST.get('role', 'customer')
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')

        # Validation
        errors = []
        if not first_name:
            errors.append('First name is required.')
        if not phone_number:
            errors.append('Phone number is required.')
        if not username:
            errors.append('Username is required.')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if password != password_confirm:
            errors.append('Passwords do not match.')
        if User.objects.filter(phone_number=phone_number).exists():
            errors.append('This phone number is already registered.')
        if User.objects.filter(username=username).exists():
            errors.append('This username is already taken.')

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'accounts/register.html', {
                'form_data': request.POST,
                'step': 1
            })

        # Store in session for step 2
        request.session['registration'] = {
            'first_name': first_name,
            'last_name': last_name,
            'username': username,
            'phone_number': phone_number,
            'email': email,
            'role': role,
            'password': password,
        }

        # Send OTP to phone number
        verification_id, otp_code = create_otp_verification(
            phone_number, purpose='verification'
        )
        request.session['otp_verification_id'] = verification_id

        messages.success(request, f'OTP sent to {phone_number}. Check the server console for the code.')
        return redirect('accounts:register_step2')

    return render(request, 'accounts/register.html', {'step': 1})


def register_step2(request):
    """
    Step 2: OTP verification.
    User enters the OTP sent to their phone.
    """
    registration_data = request.session.get('registration')
    if not registration_data:
        messages.error(request, 'Session expired. Please start registration again.')
        return redirect('accounts:register')

    if request.method == 'POST':
        otp_code = request.POST.get('otp', '').strip()

        if len(otp_code) != 6:
            messages.error(request, 'Please enter a valid 6-digit OTP.')
            return render(request, 'accounts/otp_verify.html', {
                'phone_number': registration_data['phone_number'],
                'purpose': 'registration',
                'otp_expiry_minutes': OTP_EXPIRY_MINUTES,
            })

        success, message = verify_otp(
            registration_data['phone_number'],
            otp_code,
            purpose='verification'
        )

        if success:
            # Create the user
            user = User.objects.create_user(
                username=registration_data['username'],
                email=registration_data.get('email', ''),
                first_name=registration_data['first_name'],
                last_name=registration_data['last_name'],
                phone_number=registration_data['phone_number'],
                role=registration_data['role'],
                password=registration_data['password'],
            )
            user.is_phone_verified = True
            user.save(update_fields=['is_phone_verified'])

            # Clean up session
            del request.session['registration']
            if 'otp_verification_id' in request.session:
                del request.session['otp_verification_id']

            # Log in the user
            login(request, user)
            messages.success(
                request,
                f'Welcome to Gig Saarthi, {user.first_name or user.username}!'
            )

            # Redirect based on role
            if user.role == 'worker':
                return redirect('workers:onboarding')
            elif user.role == 'customer':
                return redirect('customers:onboarding')
            return redirect('core:dashboard')
        else:
            messages.error(request, message)
            return render(request, 'accounts/otp_verify.html', {
                'phone_number': registration_data['phone_number'],
                'purpose': 'registration',
                'otp_expiry_minutes': OTP_EXPIRY_MINUTES,
            })

    # GET — show OTP form
    return render(request, 'accounts/otp_verify.html', {
        'phone_number': registration_data['phone_number'],
        'purpose': 'registration',
        'otp_expiry_minutes': OTP_EXPIRY_MINUTES,
    })


def register_resend_otp(request):
    """Resend OTP during registration."""
    registration_data = request.session.get('registration')
    if not registration_data:
        messages.error(request, 'Session expired. Please start registration again.')
        return redirect('accounts:register')

    phone_number = registration_data['phone_number']
    verification_id, otp_code = create_otp_verification(phone_number, purpose='verification')
    request.session['otp_verification_id'] = verification_id

    messages.success(request, f'New OTP sent to {phone_number}. Check the server console.')
    return redirect('accounts:register_step2')


# Keep the old register URL pointing to step 1
register = register_step1


# ── Login Flow ─────────────────────────────────────────────────────

def login_view(request):
    """
    Login with username/password OR phone + OTP.
    Includes rate limiting to prevent brute-force attacks.
    """
    # Rate limit: max 10 login attempts per minute
    rl_key = rate_limit_key(request, 'login')
    allowed, remaining, retry_after = check_rate_limit(rl_key, max_requests=10, window_seconds=60)
    if not allowed:
        messages.error(
            request,
            f'Too many login attempts. Please try again in {retry_after} seconds.'
        )
        return render(request, 'accounts/login.html')

    if request.method == 'POST':
        login_method = request.POST.get('login_method', 'password')

        if login_method == 'otp':
            # OTP Login flow
            phone_number = request.POST.get('phone_number', '').strip()
            otp_code = request.POST.get('otp', '').strip()

            if not phone_number:
                messages.error(request, 'Phone number is required.')
                return render(request, 'accounts/login.html')

            if otp_code:
                # Verify OTP
                success, message = verify_otp(phone_number, otp_code, purpose='login')
                if success:
                    try:
                        user = User.objects.get(phone_number=phone_number)
                        login(request, user)
                        messages.success(request, f'Welcome back, {user.first_name or user.username}!')
                        return redirect('core:dashboard')
                    except User.DoesNotExist:
                        messages.error(request, 'No account found with this phone number. Please register first.')
                else:
                    messages.error(request, message)
                    return render(request, 'accounts/login.html', {
                        'otp_sent': True,
                        'phone_number': phone_number,
                        'login_method': 'otp',
                    })
            else:
                # Send OTP
                try:
                    User.objects.get(phone_number=phone_number)
                except User.DoesNotExist:
                    messages.error(request, 'No account found with this phone number. Please register first.')
                    return render(request, 'accounts/login.html')

                verification_id, otp_code = create_otp_verification(phone_number, purpose='login')
                messages.success(request, f'OTP sent to {phone_number}. Check the server console.')
                return render(request, 'accounts/login.html', {
                    'otp_sent': True,
                    'phone_number': phone_number,
                    'login_method': 'otp',
                })

        else:
            # Password Login flow
            username = request.POST.get('username', '').strip()
            password = request.POST.get('password', '')
            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {user.first_name or user.username}!')
                return redirect('core:dashboard')
            else:
                messages.error(request, 'Invalid username or password.')

    return render(request, 'accounts/login.html')


def logout_view(request):
    """
    Log out the user via GET or POST request, clear session, and redirect to home.
    """
    if request.user.is_authenticated:
        logout(request)
        messages.success(request, 'You have been successfully logged out.')
    return redirect('core:home')


# ── Profile Management ─────────────────────────────────────────────

@login_required
def profile(request):
    """User profile page with edit capability."""
    user = request.user
    profile_data = None
    insurance = None
    welfare_fund = None

    if user.is_worker:
        from workers.models import WorkerProfile, WorkerInsurance
        profile_data, _ = WorkerProfile.objects.get_or_create(user=user)
        insurance = WorkerInsurance.objects.filter(
            worker=profile_data
        ).order_by('-valid_till')

        # Calculate cooperative welfare fund contribution from completed bookings
        from payments.models import Invoice
        from django.db.models import Sum
        total_platform_fee = Invoice.objects.filter(
            booking__worker=user,
            status='paid',
        ).aggregate(total=Sum('platform_fee'))['total'] or 0
        welfare_fund = {
            'total_contributed': float(total_platform_fee),
            'insurance_pool': round(float(total_platform_fee) * 0.60, 2),
            'emergency_fund': round(float(total_platform_fee) * 0.25, 2),
            'reserve': round(float(total_platform_fee) * 0.15, 2),
        }
    elif user.is_customer:
        from customers.models import CustomerProfile
        profile_data, _ = CustomerProfile.objects.get_or_create(user=user)

    context = {
        'profile_data': profile_data,
        'insurance': insurance,
        'welfare_fund': welfare_fund,
    }
    return render(request, 'accounts/profile.html', context)


@login_required
def profile_edit(request):
    """Edit user profile fields."""
    user = request.user

    if request.method == 'POST':
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.preferred_language = request.POST.get('preferred_language', user.preferred_language)

        if 'profile_photo' in request.FILES:
            photo = request.FILES['profile_photo']
            is_valid, error = validate_file_upload(photo, 'profile_photo')
            if not is_valid:
                messages.error(request, f'Photo upload failed: {error}')
                return redirect('accounts:profile_edit')
            user.profile_photo = photo

        user.save()

        # Update role-specific profile
        if user.is_worker:
            from workers.models import WorkerProfile
            profile, _ = WorkerProfile.objects.get_or_create(user=user)
            profile.bio = request.POST.get('bio', profile.bio)
            experience = request.POST.get('experience_years', profile.experience_years)
            try:
                profile.experience_years = int(experience)
            except (ValueError, TypeError):
                pass
            profile.save()
        elif user.is_customer:
            from customers.models import CustomerProfile
            profile, _ = CustomerProfile.objects.get_or_create(user=user)
            profile.default_address = request.POST.get('default_address', profile.default_address)
            try:
                profile.default_latitude = float(request.POST.get('latitude', profile.default_latitude))
                profile.default_longitude = float(request.POST.get('longitude', profile.default_longitude))
            except (ValueError, TypeError):
                pass
            profile.save()

        messages.success(request, 'Profile updated successfully!')
        return redirect('accounts:profile')

    return render(request, 'accounts/profile_edit.html')


@login_required
def change_password(request):
    """Change password page."""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Password changed successfully!')
            return redirect('accounts:profile')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'accounts/change_password.html', {'form': form})
