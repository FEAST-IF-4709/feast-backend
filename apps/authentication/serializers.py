from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password


class StaffLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class CustomerLoginSerializer(serializers.Serializer):
    phone = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if not attrs.get("phone") and not attrs.get("email"):
            raise serializers.ValidationError("Phone or email is required.")
        return attrs


class CustomerRegisterSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    email = serializers.EmailField(required=False, allow_blank=True)
    full_name = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, validators=[validate_password])


class TokenRefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class TokenResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
