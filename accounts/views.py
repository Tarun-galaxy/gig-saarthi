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

from datetime import datetime, timedelta
from django.utils import timezone
from django.core.files.storage import default_storage


def register_step1(request):
    """
    Step 1: User fills in basic info, DOB, role selection, ID verification & profile photo.
    Session stores form data between steps.
    """
    today = timezone.now().date()
    max_dob_date = (today - timedelta(days=int(18 * 365.25))).strftime('%Y-%m-%d')

    if request.method == 'POST':
        # Validate basic fields
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        username = request.POST.get('username', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        email = request.POST.get('email', '').strip()
        role = request.POST.get('role', 'customer')
        gender = request.POST.get('gender', '').strip()
        dob_str = request.POST.get('date_of_birth', '').strip()
        id_proof_type = request.POST.get('id_proof_type', '').strip()
        id_proof_number = request.POST.get('id_proof_number', '').strip()
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

        # Date of birth & age validation
        dob_val = None
        if dob_str:
            try:
                dob_val = datetime.strptime(dob_str, '%Y-%m-%d').date()
                age = today.year - dob_val.year - ((today.month, today.day) < (dob_val.month, dob_val.day))
                if age < 18:
                    errors.append('You must be at least 18 years of age to register on Gig Saarthi.')
                elif age > 110:
                    errors.append('Please provide a valid date of birth.')
            except ValueError:
                errors.append('Invalid date of birth format.')

        # ID Number format validation
        if id_proof_type and id_proof_number:
            clean_num = id_proof_number.replace(' ', '').replace('-', '').upper()
            if id_proof_type == 'Aadhaar' and (len(clean_num) != 12 or not clean_num.isdigit()):
                errors.append('Aadhaar number must be exactly 12 numeric digits.')
            elif id_proof_type == 'PAN' and len(clean_num) != 10:
                errors.append('PAN number must be exactly 10 alphanumeric characters (e.g. ABCDE1234F).')

        # Handle file uploads (profile photo & ID document)
        saved_photo_path = ''
        saved_id_doc_path = ''
        
        if 'profile_photo' in request.FILES:
            photo_file = request.FILES['profile_photo']
            try:
                saved_photo_path = default_storage.save(f'profiles/{username}_{photo_file.name}', photo_file)
            except Exception as e:
                pass

        if 'id_proof_file' in request.FILES:
            doc_file = request.FILES['id_proof_file']
            try:
                saved_id_doc_path = default_storage.save(f'documents/id/{username}_{doc_file.name}', doc_file)
            except Exception as e:
                pass

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'accounts/register.html', {
                'form_data': request.POST,
                'step': 1,
                'max_dob_date': max_dob_date,
            })

        # Store in session for step 2
        request.session['registration'] = {
            'first_name': first_name,
            'last_name': last_name,
            'username': username,
            'phone_number': phone_number,
            'email': email,
            'role': role,
            'gender': gender,
            'date_of_birth': dob_str,
            'id_proof_type': id_proof_type,
            'id_proof_number': id_proof_number,
            'profile_photo_path': saved_photo_path,
            'id_proof_file_path': saved_id_doc_path,
            'password': password,
        }

        # Send OTP to phone number
        verification_id, otp_code = create_otp_verification(
            phone_number, purpose='verification'
        )
        request.session['otp_verification_id'] = verification_id

        messages.success(request, f'OTP sent to {phone_number}. Check the server console for the code.')
        return redirect('accounts:register_step2')

    return render(request, 'accounts/register.html', {
        'step': 1,
        'max_dob_date': max_dob_date,
    })


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
            # Parse DOB if provided
            dob_val = None
            if registration_data.get('date_of_birth'):
                try:
                    dob_val = datetime.strptime(registration_data['date_of_birth'], '%Y-%m-%d').date()
                except ValueError:
                    pass

            # Create the user
            user = User.objects.create_user(
                username=registration_data['username'],
                email=registration_data.get('email', ''),
                first_name=registration_data['first_name'],
                last_name=registration_data['last_name'],
                phone_number=registration_data['phone_number'],
                role=registration_data['role'],
                gender=registration_data.get('gender', ''),
                date_of_birth=dob_val,
                password=registration_data['password'],
            )
            user.is_phone_verified = True
            
            # Attach profile photo if uploaded during step 1
            if registration_data.get('profile_photo_path'):
                user.profile_photo = registration_data['profile_photo_path']
            
            user.save()

            # Attach ID proof to worker/customer profile if uploaded
            if user.is_worker:
                from workers.models import WorkerProfile
                worker_prof, _ = WorkerProfile.objects.get_or_create(user=user)
                if registration_data.get('id_proof_type'):
                    worker_prof.id_proof_type = registration_data['id_proof_type']
                if registration_data.get('id_proof_file_path'):
                    worker_prof.id_proof_file = registration_data['id_proof_file_path']
                worker_prof.save()

            # Clean up session
            del request.session['registration']
            if 'otp_verification_id' in request.session:
                del request.session['otp_verification_id']

            # Log in the user
            login(request, user)
            messages.success(
                request,
                f'Welcome to Gig Saarthi, {user.first_name or user.username}! 🎉'
            )

            # Redirect based on role
            if user.role == 'worker':
                return redirect('workers:onboarding')
            elif user.role == 'customer':
                return redirect('customers:onboarding')
            return redirect('core:dashboard')

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

            # Flexible phone user lookup (exact, normalized, or last 10 digits)
            def find_user(p_num):
                u = User.objects.filter(phone_number=p_num).first()
                if u:
                    return u
                digits = ''.join(c for c in p_num if c.isdigit())
                if len(digits) >= 10:
                    return User.objects.filter(phone_number__endswith=digits[-10:]).first()
                return None

            user = find_user(phone_number)

            if otp_code:
                # Verify OTP
                success, message = verify_otp(phone_number, otp_code, purpose='login')
                if success:
                    if user:
                        login(request, user)
                        messages.success(request, f'Welcome back, {user.first_name or user.username}!')
                        return redirect('core:dashboard')
                    else:
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
                if not user:
                    messages.error(request, 'No account found with this phone number. Please register first.')
                    return render(request, 'accounts/login.html')

                verification_id, otp_code = create_otp_verification(user.phone_number, purpose='login')
                messages.success(request, f'OTP sent to {user.phone_number}. Check the server console.')
                return render(request, 'accounts/login.html', {
                    'otp_sent': True,
                    'phone_number': user.phone_number,
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
    try:
        if request.user.is_authenticated:
            logout(request)
            messages.success(request, 'You have been successfully logged out.')
    except Exception:
        try:
            request.session.flush()
        except Exception:
            pass
        messages.success(request, 'You have been successfully logged out.')
    return redirect('core:home')


# ── Profile Management ─────────────────────────────────────────────

@login_required
def profile(request):
    """User profile page with edit capability."""
    user = request.user
    profile_data = None
    insurance = None
    pending_insurance = None
    welfare_fund = None
    masked_account = ''
    certifications = []

    if user.is_worker:
        from workers.models import WorkerProfile, WorkerInsurance
        profile_data, _ = WorkerProfile.objects.get_or_create(user=user)
        
        # Only active approved policies generate the official physical ID card
        insurance = WorkerInsurance.objects.filter(
            worker=profile_data,
            status='active'
        ).order_by('-valid_till')

        # Pending application awaiting admin approval
        pending_insurance = WorkerInsurance.objects.filter(
            worker=profile_data,
            status='pending'
        ).order_by('-created_at').first()

        certifications = profile_data.certifications.select_related('skill').all()

        if profile_data.bank_account_number:
            acc = str(profile_data.bank_account_number)
            masked_account = '•••• •••• ' + acc[-4:] if len(acc) >= 4 else acc

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
        'pending_insurance': pending_insurance,
        'certifications': certifications,
        'masked_account': masked_account,
        'welfare_fund': welfare_fund,
    }
    return render(request, 'accounts/profile.html', context)



@login_required
def profile_edit(request):
    """Edit user profile fields including skills, documents, and payout/bank details."""
    user = request.user
    profile_data = None
    skill_categories = []
    worker_skill_ids = set()
    certifications = []
    cooperatives = []
    all_skills = []

    from workers.models import WorkerProfile, Skill, SkillCategory, Certification
    from cooperative_admin.models import Cooperative
    from customers.models import CustomerProfile

    if user.is_worker:
        profile_data, _ = WorkerProfile.objects.get_or_create(user=user)
        skill_categories = SkillCategory.objects.prefetch_related('skills').all()
        worker_skill_ids = set(profile_data.skills.values_list('id', flat=True))
        certifications = profile_data.certifications.select_related('skill').all()
        cooperatives = Cooperative.objects.filter(is_active=True)
        all_skills = Skill.objects.select_related('category').all().order_by('name')
    elif user.is_customer:
        profile_data, _ = CustomerProfile.objects.get_or_create(user=user)

    if request.method == 'POST':
        action = request.POST.get('action', 'save_all')

        # Handle certificate deletion
        if action == 'delete_certificate':
            cert_id = request.POST.get('certificate_id')
            if cert_id and user.is_worker:
                Certification.objects.filter(id=cert_id, worker=profile_data).delete()
                messages.success(request, 'Certificate removed successfully.')
                return redirect(f"{request.path}?tab=documents")

        # 1. Update basic user info
        user.first_name = request.POST.get('first_name', user.first_name).strip()
        user.last_name = request.POST.get('last_name', user.last_name).strip()
        user.email = request.POST.get('email', user.email).strip()
        user.preferred_language = request.POST.get('preferred_language', user.preferred_language)

        gender_val = request.POST.get('gender', '').strip()
        if gender_val in ('male', 'female', 'other'):
            user.gender = gender_val

        dob_str = request.POST.get('date_of_birth', '').strip()
        if dob_str:
            try:
                user.date_of_birth = datetime.strptime(dob_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        if 'profile_photo' in request.FILES:
            photo = request.FILES['profile_photo']
            is_valid, error = validate_file_upload(photo, 'profile_photo')
            if not is_valid:
                messages.error(request, f'Photo upload failed: {error}')
                return redirect('accounts:profile_edit')
            user.profile_photo = photo

        user.save()

        # 2. Update role-specific fields
        if user.is_worker and profile_data:
            # Basic work details
            profile_data.bio = request.POST.get('bio', profile_data.bio).strip()
            exp = request.POST.get('experience_years', profile_data.experience_years)
            try:
                profile_data.experience_years = max(0, int(exp))
            except (ValueError, TypeError):
                pass
            
            avail = request.POST.get('availability_status')
            if avail in ('available', 'busy', 'offline'):
                profile_data.availability_status = avail

            coop_id = request.POST.get('cooperative')
            if coop_id:
                profile_data.cooperative = Cooperative.objects.filter(id=coop_id).first()
            elif 'cooperative' in request.POST:
                profile_data.cooperative = None

            # Trade Skills (if skills field is present in submission)
            if 'skills' in request.POST or action == 'save_skills':
                skill_ids = request.POST.getlist('skills')
                profile_data.skills.set(Skill.objects.filter(id__in=skill_ids))

            # KYC & ID Documents
            id_type = request.POST.get('id_proof_type')
            if id_type is not None:
                profile_data.id_proof_type = id_type

            if 'id_proof_file' in request.FILES:
                id_file = request.FILES['id_proof_file']
                is_valid, error = validate_file_upload(id_file, 'id_proof')
                if not is_valid:
                    messages.error(request, f'ID document upload failed: {error}')
                    return redirect(f"{request.path}?tab=documents")
                profile_data.id_proof_file = id_file

            # Bank & Direct Payout Details
            bank_name = request.POST.get('bank_name')
            if bank_name is not None:
                profile_data.bank_name = bank_name.strip()
            
            acc_num = request.POST.get('bank_account_number')
            if acc_num is not None:
                profile_data.bank_account_number = acc_num.strip()

            ifsc = request.POST.get('bank_ifsc_code')
            if ifsc is not None:
                profile_data.bank_ifsc_code = ifsc.strip().upper()

            upi = request.POST.get('upi_id')
            if upi is not None:
                profile_data.upi_id = upi.strip()

            # New Certificate Upload
            if 'certificate_file' in request.FILES:
                cert_file = request.FILES['certificate_file']
                cert_name = request.POST.get('certificate_name', '').strip()
                cert_skill_id = request.POST.get('certificate_skill')
                cert_issuer = request.POST.get('certificate_issued_by', '').strip()
                cert_date = request.POST.get('certificate_issue_date')

                if cert_name and cert_skill_id:
                    is_valid, error = validate_file_upload(cert_file, 'certificate')
                    if not is_valid:
                        messages.error(request, f'Certificate upload failed: {error}')
                        return redirect(f"{request.path}?tab=documents")
                    
                    target_skill = Skill.objects.filter(id=cert_skill_id).first()
                    if target_skill:
                        Certification.objects.create(
                            worker=profile_data,
                            skill=target_skill,
                            certificate_name=cert_name,
                            certificate_file=cert_file,
                            issued_by=cert_issuer,
                            issue_date=cert_date or None,
                        )
                        messages.success(request, f'Certificate "{cert_name}" uploaded successfully.')

            profile_data.save()

        elif user.is_customer and profile_data:
            profile_data.default_address = request.POST.get('default_address', profile_data.default_address)
            try:
                profile_data.default_latitude = float(request.POST.get('latitude', profile_data.default_latitude))
                profile_data.default_longitude = float(request.POST.get('longitude', profile_data.default_longitude))
            except (ValueError, TypeError):
                pass
            profile_data.save()

        messages.success(request, 'Profile updated successfully!')
        
        active_tab = request.POST.get('active_tab')
        if active_tab and active_tab != 'basic':
            return redirect(f"{request.path}?tab={active_tab}")
        return redirect('accounts:profile')

    selected_tab = request.GET.get('tab', 'basic')
    id_proof_types = [
        'Aadhaar Card',
        'PAN Card',
        'Voter ID Card',
        'Driving License',
        'Passport',
        'Labour / E-Shram Card',
    ]

    masked_account = ''
    if profile_data and hasattr(profile_data, 'bank_account_number') and profile_data.bank_account_number:
        acc = str(profile_data.bank_account_number)
        masked_account = '•••• •••• ' + acc[-4:] if len(acc) >= 4 else acc

    context = {
        'profile_data': profile_data,
        'skill_categories': skill_categories,
        'worker_skill_ids': worker_skill_ids,
        'certifications': certifications,
        'cooperatives': cooperatives,
        'all_skills': all_skills,
        'id_proof_types': id_proof_types,
        'selected_tab': selected_tab,
        'masked_account': masked_account,
        'max_dob_date': (timezone.now().date() - timedelta(days=int(18 * 365.25))).strftime('%Y-%m-%d'),
    }
    return render(request, 'accounts/profile_edit.html', context)



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
