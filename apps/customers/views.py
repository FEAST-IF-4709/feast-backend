from datetime import timedelta

from django.db import transaction as db_transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from rest_framework import status as http_status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from apps.customers.models import Customer, LoyaltyAccount, CustomerVoucher, VoucherTemplate
from apps.customers.serializers import (
    CustomerPublicSerializer,
    CustomerProfileSerializer,
    CustomerUpdateSerializer,
    LoyaltyAccountSerializer,
    CustomerVoucherSerializer,
    RedeemVoucherSerializer,
    VoucherTemplateSerializer,
    VoucherTemplateWriteSerializer,
)
from core.responses.standard import StandardResponse
from core.schema import COMMON_ERROR_RESPONSES
from core.viewsets.tenant_scoped import TenantScopedViewSet


class CustomerSearchView(APIView):
    """GET /api/v1/customers/search/?phone=<phone> — Cashier lookup by exact phone number."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Customers"],
        summary="Search customer by phone",
        description="Exact-match lookup of a customer by phone number. Used by cashiers to link a customer to a POS order. Requires `customer.view` permission.",
        parameters=[OpenApiParameter("phone", str, required=True, description="Customer phone number (exact match)")],
        responses={200: CustomerPublicSerializer, **COMMON_ERROR_RESPONSES},
    )
    def get(self, request):
        tenant = getattr(request, "tenant", None)
        if not tenant or tenant.get("actor_type") != "EMPLOYEE":
            return StandardResponse(
                success=False, code="PERMISSION_DENIED",
                message="Only employees can search customers.",
                status=403, request=request,
            )
        if "customer.view" not in tenant.get("permissions", frozenset()):
            return StandardResponse(
                success=False, code="PERMISSION_DENIED",
                message="Missing permission: customer.view",
                status=403, request=request,
            )

        phone = request.query_params.get("phone", "").strip()
        if not phone:
            return StandardResponse(
                success=False, code="VALIDATION_ERROR",
                message="Query param 'phone' wajib diisi.",
                status=400, request=request,
            )

        customer = Customer.objects.filter(phone=phone, is_active=True).first()
        if not customer:
            return StandardResponse(
                success=False, code="NOT_FOUND",
                message="Customer tidak ditemukan.",
                status=404, request=request,
            )

        return StandardResponse(
            data=CustomerPublicSerializer(customer).data,
            request=request,
        )


class CustomerMeView(APIView):
    """GET/PATCH /api/v1/customers/me/ — Customer self-serve profile."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        tags=["Customers"],
        summary="Get own profile",
        description="Retrieve the authenticated customer's profile. Requires customer JWT.",
        responses={200: CustomerProfileSerializer, **COMMON_ERROR_RESPONSES},
    )
    def get(self, request):
        tenant = getattr(request, "tenant", None)
        if not tenant or tenant.get("actor_type") != "CUSTOMER":
            return StandardResponse(
                success=False, code="PERMISSION_DENIED",
                message="Endpoint ini hanya untuk customer.",
                status=403, request=request,
            )

        return StandardResponse(
            data=CustomerProfileSerializer(request.user, context={"request": request}).data,
            request=request,
        )

    @extend_schema(
        tags=["Customers"],
        summary="Update own profile",
        description="Partial update of the authenticated customer's profile (full_name, email, profile_photo). Requires customer JWT.",
        request=CustomerUpdateSerializer,
        responses={200: CustomerProfileSerializer, **COMMON_ERROR_RESPONSES},
    )
    def patch(self, request):
        tenant = getattr(request, "tenant", None)
        if not tenant or tenant.get("actor_type") != "CUSTOMER":
            return StandardResponse(
                success=False, code="PERMISSION_DENIED",
                message="Endpoint ini hanya untuk customer.",
                status=403, request=request,
            )

        serializer = CustomerUpdateSerializer(
            request.user, data=request.data, partial=True, context={"request": request}
        )
        if not serializer.is_valid():
            return StandardResponse(
                success=False, code="VALIDATION_ERROR",
                message=serializer.errors,
                status=400, request=request,
            )

        serializer.save()

        return StandardResponse(
            data=CustomerProfileSerializer(request.user, context={"request": request}).data,
            message="Profil berhasil diperbarui.",
            request=request,
        )


class CustomerLoyaltyView(APIView):
    """GET /api/v1/customers/me/loyalty/ — Customer loyalty balance + transaction history."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Customers"],
        summary="Get loyalty account",
        description="Retrieve the authenticated customer's loyalty point balance, tier, and last 50 transactions. Requires customer JWT.",
        responses={200: LoyaltyAccountSerializer, **COMMON_ERROR_RESPONSES},
    )
    def get(self, request):
        tenant = getattr(request, "tenant", None)
        if not tenant or tenant.get("actor_type") != "CUSTOMER":
            return StandardResponse(
                success=False, code="PERMISSION_DENIED",
                message="Endpoint ini hanya untuk customer.",
                status=403, request=request,
            )

        account, _ = LoyaltyAccount.objects.get_or_create(customer=request.user)
        account_data = LoyaltyAccountSerializer(account).data
        account_data["transactions"] = account_data["transactions"][:50]

        return StandardResponse(data=account_data, request=request)


class CustomerVoucherListView(APIView):
    """GET /api/v1/customers/me/vouchers/ — List customer-owned vouchers."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Customers"],
        summary="List owned vouchers",
        description="List all vouchers owned by the authenticated customer. Filter by status with ?status=AVAILABLE|USED|EXPIRED.",
        parameters=[OpenApiParameter("status", str, required=False, description="Filter by voucher status")],
        responses={200: CustomerVoucherSerializer(many=True), **COMMON_ERROR_RESPONSES},
    )
    def get(self, request):
        tenant = getattr(request, "tenant", None)
        if not tenant or tenant.get("actor_type") != "CUSTOMER":
            return StandardResponse(
                success=False, code="PERMISSION_DENIED",
                message="Endpoint ini hanya untuk customer.",
                status=403, request=request,
            )

        qs = (
            CustomerVoucher.objects
            .filter(customer=request.user)
            .select_related("voucher_template")
            .prefetch_related("voucher_template__applicable_categories", "voucher_template__applicable_products")
            .order_by("-created_at")
        )

        status_filter = request.query_params.get("status", "").strip().upper()
        if status_filter in CustomerVoucher.Status.values:
            qs = qs.filter(status=status_filter)

        return StandardResponse(
            data=CustomerVoucherSerializer(qs, many=True).data,
            request=request,
        )


class RedeemVoucherView(APIView):
    """POST /api/v1/customers/me/vouchers/redeem/ — Redeem loyalty points for a voucher."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Customers"],
        summary="Redeem points for a voucher",
        description="Exchange loyalty points for a voucher template. Deducts points and creates an owned CustomerVoucher.",
        request=RedeemVoucherSerializer,
        responses={201: CustomerVoucherSerializer, **COMMON_ERROR_RESPONSES},
    )
    def post(self, request):
        tenant = getattr(request, "tenant", None)
        if not tenant or tenant.get("actor_type") != "CUSTOMER":
            return StandardResponse(
                success=False, code="PERMISSION_DENIED",
                message="Endpoint ini hanya untuk customer.",
                status=403, request=request,
            )

        serializer = RedeemVoucherSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        template = serializer._template

        with db_transaction.atomic():
            account, _ = LoyaltyAccount.objects.select_for_update().get_or_create(customer=request.user)

            if account.points_balance < template.points_cost:
                return StandardResponse(
                    success=False, code="INSUFFICIENT_POINTS",
                    message=f"Poin tidak cukup. Dibutuhkan {template.points_cost} poin, kamu punya {account.points_balance} poin.",
                    status=400, request=request,
                )

            from apps.customers.models import LoyaltyTransaction

            new_balance = account.points_balance - template.points_cost
            account.points_balance = new_balance
            account.save(update_fields=["points_balance", "updated_at"])

            LoyaltyTransaction.objects.create(
                account=account,
                txn_type=LoyaltyTransaction.TxnType.REDEEM,
                points=-template.points_cost,
                balance_after=new_balance,
                reference_type="voucher_template",
                reference_id=template.id,
                note=f"Redeem voucher: {template.title}",
            )

            expires_at = timezone.now() + timedelta(days=template.valid_days)
            voucher = CustomerVoucher.objects.create(
                customer=request.user,
                voucher_template=template,
                status=CustomerVoucher.Status.AVAILABLE,
                expires_at=expires_at,
            )

        return StandardResponse(
            data=CustomerVoucherSerializer(voucher).data,
            message="Voucher berhasil ditukar.",
            status=201,
            request=request,
        )


class VoucherCatalogView(APIView):
    """GET /api/v1/customers/voucher-catalog/ — Public voucher catalog. Optional ?brand_id= filter."""

    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Customers"],
        summary="Browse voucher catalog",
        description="List active voucher templates. Omit brand_id to get catalog from all brands.",
        parameters=[OpenApiParameter("brand_id", str, required=False, description="Brand UUID (optional)")],
        responses={200: VoucherTemplateSerializer(many=True), **COMMON_ERROR_RESPONSES},
    )
    def get(self, request):
        brand_id = request.query_params.get("brand_id", "").strip()

        qs = VoucherTemplate.objects.filter(is_active=True).select_related("brand")
        if brand_id:
            qs = qs.filter(brand_id=brand_id)

        qs = qs.prefetch_related("applicable_categories", "applicable_products").order_by("points_cost")

        return StandardResponse(
            data=VoucherTemplateSerializer(qs, many=True, context={"request": request}).data,
            request=request,
        )


@extend_schema_view(
    list=extend_schema(tags=["Loyalty"], summary="List voucher templates"),
    retrieve=extend_schema(tags=["Loyalty"], summary="Get voucher template", responses={200: VoucherTemplateSerializer, **COMMON_ERROR_RESPONSES}),
    create=extend_schema(tags=["Loyalty"], summary="Create voucher template", request=VoucherTemplateWriteSerializer, responses={201: VoucherTemplateSerializer, **COMMON_ERROR_RESPONSES}),
    update=extend_schema(tags=["Loyalty"], summary="Update voucher template", request=VoucherTemplateWriteSerializer, responses={200: VoucherTemplateSerializer, **COMMON_ERROR_RESPONSES}),
    partial_update=extend_schema(tags=["Loyalty"], summary="Partial update voucher template", request=VoucherTemplateWriteSerializer, responses={200: VoucherTemplateSerializer, **COMMON_ERROR_RESPONSES}),
    destroy=extend_schema(tags=["Loyalty"], summary="Delete voucher template", responses={204: None, **COMMON_ERROR_RESPONSES}),
)
class VoucherTemplateViewSet(TenantScopedViewSet):
    """Brand-level CRUD for voucher templates. Requires loyalty.voucher.manage permission."""

    serializer_class = VoucherTemplateSerializer
    tenant_field = "brand"
    outlet_field = None

    required_permissions = {
        "list": "loyalty.voucher.manage",
        "retrieve": "loyalty.voucher.manage",
        "create": "loyalty.voucher.manage",
        "update": "loyalty.voucher.manage",
        "partial_update": "loyalty.voucher.manage",
        "destroy": "loyalty.voucher.manage",
    }

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return VoucherTemplate.objects.none()
        return (
            VoucherTemplate.objects
            .filter(brand_id=tenant["brand_id"])
            .prefetch_related("applicable_categories", "applicable_products")
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return VoucherTemplateWriteSerializer
        return VoucherTemplateSerializer

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        return StandardResponse(
            data=VoucherTemplateSerializer(qs, many=True, context={"request": request}).data,
            request=request,
        )

    def create(self, request, *args, **kwargs):
        serializer = VoucherTemplateWriteSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        template = serializer.save(brand_id=request.tenant["brand_id"])
        return StandardResponse(
            data=VoucherTemplateSerializer(template, context={"request": request}).data,
            message="Voucher template berhasil dibuat.",
            status=http_status.HTTP_201_CREATED,
            request=request,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = VoucherTemplateWriteSerializer(instance, data=request.data, partial=partial, context={"request": request})
        serializer.is_valid(raise_exception=True)
        template = serializer.save()
        return StandardResponse(
            data=VoucherTemplateSerializer(template, context={"request": request}).data,
            message="Voucher template berhasil diperbarui.",
            request=request,
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            instance.delete()
        except ProtectedError:
            return StandardResponse(
                success=False,
                code="CONFLICT",
                message="Voucher template tidak bisa dihapus karena sudah pernah ditukar oleh customer.",
                status=http_status.HTTP_409_CONFLICT,
                request=request,
            )
        return StandardResponse(
            message="Voucher template berhasil dihapus.",
            status=http_status.HTTP_204_NO_CONTENT,
            request=request,
        )
