"""Accounts serializers for DRF API — registration, OTP, login, profile."""

from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration with role selection."""

    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'phone_number', 'role', 'password', 'password_confirm',
            'preferred_language'
        ]

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        if User.objects.filter(phone_number=data['phone_number']).exists():
            raise serializers.ValidationError({"phone_number": "This phone number is already registered."})
        if User.objects.filter(username=data['username']).exists():
            raise serializers.ValidationError({"username": "This username is already taken."})
        return data


class OTPRequestSerializer(serializers.Serializer):
    """Serializer for requesting an OTP."""

    phone_number = serializers.CharField(max_length=15)
    purpose = serializers.ChoiceField(
        choices=['verification', 'login', 'password_reset'],
        default='login'
    )


class OTPVerifySerializer(serializers.Serializer):
    """Serializer for verifying an OTP."""

    phone_number = serializers.CharField(max_length=15)
    otp = serializers.CharField(min_length=6, max_length=6)
    purpose = serializers.ChoiceField(
        choices=['verification', 'login', 'password_reset'],
        default='login'
    )


class LoginSerializer(serializers.Serializer):
    """Serializer for password-based login."""

    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class JWTTokenResponseSerializer(serializers.Serializer):
    """Serializer for JWT token response."""

    access = serializers.CharField()
    refresh = serializers.CharField()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for reading/updating user profile."""

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'full_name', 'role', 'phone_number', 'preferred_language',
            'is_phone_verified', 'profile_photo', 'date_joined'
        ]
        read_only_fields = ['id', 'username', 'role', 'date_joined', 'is_phone_verified']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class UserMinimalSerializer(serializers.ModelSerializer):
    """Minimal user info for nested serialization."""

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'full_name', 'role', 'profile_photo']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username
