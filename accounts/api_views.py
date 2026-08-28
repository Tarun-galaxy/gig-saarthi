"""Accounts API views for DRF — OTP registration, verification, JWT login, profile."""

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate, get_user_model
from .serializers import (
    UserRegistrationSerializer, UserSerializer,
    OTPRequestSerializer, OTPVerifySerializer,
    LoginSerializer, JWTTokenResponseSerializer
)
from core.services.otp import create_otp_verification, verify_otp, OTP_EXPIRY_MINUTES

User = get_user_model()


class RegisterView(APIView):
    """
    Step 1 of registration: submit user details and receive OTP.
    POST: {first_name, last_name, username, phone_number, role, password, password_confirm}
    Returns: {message, phone_number, otp_expiry_minutes}
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Store validated data in session for step 2
        # (In API context, we use a simple approach: store in a server-side dict keyed by phone)
        validated = serializer.validated_data.copy()
        phone = validated['phone_number']

        # Send OTP
        verification_id, otp_code = create_otp_verification(phone, purpose='verification')

        return Response({
            "message": f"OTP sent to {phone}. Check server console for code.",
            "phone_number": phone,
            "otp_expiry_minutes": OTP_EXPIRY_MINUTES,
            "next_step": "/api/auth/register/verify/",
            "registration_data": {
                "username": validated["username"],
                "first_name": validated.get("first_name", ""),
                "last_name": validated.get("last_name", ""),
                "email": validated.get("email", ""),
                "phone_number": phone,
                "role": validated["role"],
                "preferred_language": validated.get("preferred_language", "en"),
            }
        }, status=status.HTTP_200_OK)


class RegisterVerifyView(APIView):
    """
    Step 2 of registration: verify OTP and create user.
    POST: {otp, registration_data}
    Returns: {user, tokens}
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        otp_code = request.data.get('otp', '').strip()
        reg_data = request.data.get('registration_data', {})

        if not otp_code or len(otp_code) != 6:
            return Response(
                {"error": "Please enter a valid 6-digit OTP."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not reg_data or 'phone_number' not in reg_data:
            return Response(
                {"error": "Registration data missing. Please restart registration."},
                status=status.HTTP_400_BAD_REQUEST
            )

        phone = reg_data['phone_number']

        # Check if user already exists
        if User.objects.filter(phone_number=phone).exists():
            return Response(
                {"error": "This phone number is already registered."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify OTP
        success, message = verify_otp(phone, otp_code, purpose='verification')
        if not success:
            return Response(
                {"error": message},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create user
        password = reg_data.pop('password', None)
        if not password:
            return Response(
                {"error": "Password is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.create_user(
            username=reg_data['username'],
            email=reg_data.get('email', ''),
            first_name=reg_data.get('first_name', ''),
            last_name=reg_data.get('last_name', ''),
            phone_number=phone,
            role=reg_data.get('role', 'customer'),
            preferred_language=reg_data.get('preferred_language', 'en'),
            password=password,
        )
        user.is_phone_verified = True
        user.save(update_fields=['is_phone_verified'])

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)

        return Response({
            "message": "Registration successful!",
            "user": UserSerializer(user).data,
            "tokens": {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }
        }, status=status.HTTP_201_CREATED)


class OTPRequestView(APIView):
    """
    Request an OTP for any purpose (login, password reset, etc.).
    POST: {phone_number, purpose}
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data['phone_number']
        purpose = serializer.validated_data.get('purpose', 'login')

        # For login, verify user exists
        if purpose == 'login':
            if not User.objects.filter(phone_number=phone).exists():
                return Response(
                    {"error": "No account found with this phone number."},
                    status=status.HTTP_404_NOT_FOUND
                )

        verification_id, otp_code = create_otp_verification(phone, purpose=purpose)

        return Response({
            "message": f"OTP sent to {phone}.",
            "otp_expiry_minutes": OTP_EXPIRY_MINUTES,
        }, status=status.HTTP_200_OK)


class OTPVerifyView(APIView):
    """
    Verify an OTP and return a JWT token (for login) or confirmation.
    POST: {phone_number, otp, purpose}
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data['phone_number']
        otp_code = serializer.validated_data['otp']
        purpose = serializer.validated_data.get('purpose', 'login')

        success, message = verify_otp(phone, otp_code, purpose=purpose)

        if not success:
            return Response(
                {"error": message},
                status=status.HTTP_400_BAD_REQUEST
            )

        # For login purpose, return JWT token
        if purpose == 'login':
            try:
                user = User.objects.get(phone_number=phone)
                refresh = RefreshToken.for_user(user)
                return Response({
                    "message": "Login successful!",
                    "user": UserSerializer(user).data,
                    "tokens": {
                        "access": str(refresh.access_token),
                        "refresh": str(refresh),
                    }
                }, status=status.HTTP_200_OK)
            except User.DoesNotExist:
                return Response(
                    {"error": "User not found."},
                    status=status.HTTP_404_NOT_FOUND
                )

        return Response({
            "message": message,
        }, status=status.HTTP_200_OK)


class LoginView(APIView):
    """
    Login with username/password.
    POST: {username, password}
    Returns: {user, tokens}
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            request,
            username=serializer.validated_data['username'],
            password=serializer.validated_data['password']
        )

        if user is None:
            return Response(
                {"error": "Invalid username or password."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        refresh = RefreshToken.for_user(user)

        return Response({
            "message": "Login successful!",
            "user": UserSerializer(user).data,
            "tokens": {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }
        }, status=status.HTTP_200_OK)


class CurrentUserView(APIView):
    """Get or update the currently authenticated user."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class UserProfileView(APIView):
    """Get user profile with role-specific details."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        data = UserSerializer(user).data

        if user.role == 'worker':
            try:
                profile = user.worker_profile
                from workers.serializers import WorkerProfileSerializer
                data['worker_profile'] = WorkerProfileSerializer(profile).data
            except Exception:
                data['worker_profile'] = None
        elif user.role == 'customer':
            try:
                profile = user.customer_profile
                from customers.serializers import CustomerProfileSerializer
                data['customer_profile'] = CustomerProfileSerializer(profile).data
            except Exception:
                data['customer_profile'] = None

        return Response(data)
