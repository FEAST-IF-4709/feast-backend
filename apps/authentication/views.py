from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status as http_status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

from core.responses.standard import StandardResponse
from apps.staff.models import Employee
from apps.customers.models import Customer
from apps.authentication.models import BlacklistedJTI
from apps.authentication.tokens import create_employee_tokens, create_customer_tokens
from apps.authentication.serializers import (
    StaffLoginSerializer,
    CustomerLoginSerializer,
    CustomerRegisterSerializer,
    LogoutSerializer,
    TokenRefreshSerializer,
)


class StaffLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = StaffLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        try:
            employee = Employee.objects.select_related("brand", "outlet", "role").get(
                email=email, is_active=True
            )
        except Employee.DoesNotExist:
            return StandardResponse(
                success=False,
                code="AUTHENTICATION_REQUIRED",
                message="Invalid credentials.",
                status=http_status.HTTP_401_UNAUTHORIZED,
                request=request,
            )

        if not employee.check_password(password):
            return StandardResponse(
                success=False,
                code="AUTHENTICATION_REQUIRED",
                message="Invalid credentials.",
                status=http_status.HTTP_401_UNAUTHORIZED,
                request=request,
            )

        tokens = create_employee_tokens(employee)
        return StandardResponse(
            data=tokens,
            message="Login successful.",
            request=request,
            status=http_status.HTTP_200_OK,
        )


class CustomerLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CustomerLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data.get("phone", "")
        email = serializer.validated_data.get("email", "")
        password = serializer.validated_data["password"]

        qs = Customer.objects.filter(is_active=True)
        if phone:
            qs = qs.filter(phone=phone)
        else:
            qs = qs.filter(email=email)

        customer = qs.first()
        if not customer or not customer.check_password(password):
            return StandardResponse(
                success=False,
                code="AUTHENTICATION_REQUIRED",
                message="Invalid credentials.",
                status=http_status.HTTP_401_UNAUTHORIZED,
                request=request,
            )

        tokens = create_customer_tokens(customer)
        return StandardResponse(
            data=tokens,
            message="Login successful.",
            request=request,
            status=http_status.HTTP_200_OK,
        )


class CustomerRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CustomerRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        if Customer.objects.filter(phone=data["phone"]).exists():
            return StandardResponse(
                success=False,
                code="VALIDATION_ERROR",
                message="Phone number already registered.",
                status=http_status.HTTP_400_BAD_REQUEST,
                request=request,
            )

        email = data.get("email") or None
        if email and Customer.objects.filter(email=email).exists():
            return StandardResponse(
                success=False,
                code="VALIDATION_ERROR",
                message="Email already registered.",
                status=http_status.HTTP_400_BAD_REQUEST,
                request=request,
            )

        customer = Customer(
            phone=data["phone"],
            email=email,
            full_name=data["full_name"],
        )
        customer.set_password(data["password"])
        customer.save()

        tokens = create_customer_tokens(customer)
        return StandardResponse(
            data=tokens,
            message="Registration successful.",
            request=request,
            status=http_status.HTTP_201_CREATED,
        )


class FeastTokenRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TokenRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            refresh = RefreshToken(serializer.validated_data["refresh"])
        except (TokenError, InvalidToken) as exc:
            return StandardResponse(
                success=False,
                code="AUTHENTICATION_REQUIRED",
                message=str(exc),
                status=http_status.HTTP_401_UNAUTHORIZED,
                request=request,
            )

        jti = refresh.get("jti")
        if jti and BlacklistedJTI.objects.filter(jti=jti).exists():
            return StandardResponse(
                success=False,
                code="TOKEN_BLACKLISTED",
                message="Token has been blacklisted.",
                status=http_status.HTTP_401_UNAUTHORIZED,
                request=request,
            )

        # Blacklist old token, issue new one with same claims
        BlacklistedJTI.objects.get_or_create(jti=jti)
        new_refresh = RefreshToken()
        for claim in ["user_id", "actor_type", "brand_id", "outlet_id", "outlet_ids", "role_id", "permissions"]:
            val = refresh.get(claim)
            if val is not None:
                new_refresh[claim] = val

        return StandardResponse(
            data={"access": str(new_refresh.access_token), "refresh": str(new_refresh)},
            message="Token refreshed.",
            request=request,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            refresh = RefreshToken(serializer.validated_data["refresh"])
            jti = refresh.get("jti")
            if jti:
                BlacklistedJTI.objects.get_or_create(jti=jti)
        except (TokenError, InvalidToken):
            pass

        return StandardResponse(
            message="Logged out successfully.",
            request=request,
            status=http_status.HTTP_200_OK,
        )
