from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status as http_status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

from core.responses.standard import StandardResponse
from core.schema import AUTH_ERROR_RESPONSES, COMMON_ERROR_RESPONSES
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
    TokenResponseSerializer,
    EmployeeMeSerializer,
)


class StaffLoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Auth"],
        summary="Staff login",
        description="Authenticate a brand employee and return JWT access + refresh tokens.",
        request=StaffLoginSerializer,
        responses={200: TokenResponseSerializer, **AUTH_ERROR_RESPONSES},
    )
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

    @extend_schema(
        tags=["Auth"],
        summary="Customer login",
        description="Authenticate a customer by phone or email and return JWT tokens.",
        request=CustomerLoginSerializer,
        responses={200: TokenResponseSerializer, **AUTH_ERROR_RESPONSES},
    )
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

    @extend_schema(
        tags=["Auth"],
        summary="Customer registration",
        description="Register a new customer account and return JWT tokens.",
        request=CustomerRegisterSerializer,
        responses={201: TokenResponseSerializer, **AUTH_ERROR_RESPONSES},
    )
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

    @extend_schema(
        tags=["Auth"],
        summary="Refresh access token",
        description="Exchange a valid refresh token for a new access + refresh token pair. The old refresh token is blacklisted.",
        request=TokenRefreshSerializer,
        responses={200: TokenResponseSerializer, **AUTH_ERROR_RESPONSES},
    )
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

        # Blacklist old token, issue fresh one with up-to-date claims from DB
        BlacklistedJTI.objects.get_or_create(jti=jti)

        actor_type = refresh.get("actor_type")
        user_id = refresh.get("user_id")

        if actor_type == "EMPLOYEE":
            try:
                employee = (
                    Employee.objects.select_related("brand", "outlet", "role")
                    .get(pk=user_id, is_active=True)
                )
            except Employee.DoesNotExist:
                return StandardResponse(
                    success=False,
                    code="AUTHENTICATION_REQUIRED",
                    message="Employee not found or inactive.",
                    status=http_status.HTTP_401_UNAUTHORIZED,
                    request=request,
                )
            new_tokens = create_employee_tokens(employee)
            return StandardResponse(data=new_tokens, message="Token refreshed.", request=request)

        # Customer / other actor types: copy claims as-is (no permission list to refresh)
        new_refresh = RefreshToken()
        for claim in ["user_id", "actor_type"]:
            val = refresh.get(claim)
            if val is not None:
                new_refresh[claim] = val

        return StandardResponse(
            data={"access": str(new_refresh.access_token), "refresh": str(new_refresh)},
            message="Token refreshed.",
            request=request,
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Auth"],
        summary="Current employee profile",
        description="Returns the authenticated employee's profile, role, and list of permission codenames.",
        responses={200: EmployeeMeSerializer, **COMMON_ERROR_RESPONSES},
    )
    def get(self, request):
        tenant = getattr(request, "tenant", None)
        if not tenant or tenant.get("actor_type") != "EMPLOYEE":
            return StandardResponse(
                success=False,
                code="PERMISSION_DENIED",
                message="Only employees can access this endpoint.",
                status=http_status.HTTP_403_FORBIDDEN,
                request=request,
            )

        employee = request.user
        outlet = getattr(employee, "outlet", None)

        data = {
            "id": employee.id,
            "email": employee.email,
            "full_name": employee.full_name,
            "outlet_id": employee.outlet_id,
            "outlet_name": outlet.name if outlet else None,
            "role": {
                "id": employee.role_id,
                "name": employee.role.name,
                "is_system": employee.role.is_system,
            },
            "permissions": sorted(tenant["permissions"]),
        }
        return StandardResponse(data=data, message="Profile retrieved.", request=request)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Auth"],
        summary="Logout",
        description="Blacklist the provided refresh token, invalidating the session.",
        request=LogoutSerializer,
        responses={200: None, **COMMON_ERROR_RESPONSES},
    )
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
