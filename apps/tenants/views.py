from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework import viewsets, status as http_status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework import serializers as drf_serializers

from core.permissions.has_permission import HasPermission
from core.responses.standard import StandardResponse
from core.viewsets.tenant_scoped import TenantScopedViewSet
from core.schema import COMMON_ERROR_RESPONSES
from drf_spectacular.utils import extend_schema, extend_schema_view
from .models import Brand, Outlet
from .serializers import BrandSerializer, BrandAdminSerializer, OutletSerializer, OutletCreateSerializer, PublicBrandSerializer, PublicOutletSerializer


class BrandAdminViewSet(viewsets.ViewSet):
    """Full Brand CRUD — SuperAdmin only. Not brand-scoped."""
    permission_classes = [IsAuthenticated, HasPermission]
    required_permissions = {}  # HasPermission allows SuperAdmin unconditionally

    def _require_superadmin(self, request):
        tenant = getattr(request, "tenant", None)
        if not tenant or not tenant.get("is_superadmin"):
            return StandardResponse(
                success=False,
                code="PERMISSION_DENIED",
                message="Only SuperAdmin can access this endpoint.",
                status=http_status.HTTP_403_FORBIDDEN,
                request=request,
            )
        return None

    @extend_schema(tags=["Admin — Brands"], summary="List all brands")
    def list(self, request):
        if err := self._require_superadmin(request):
            return err
        brands = Brand.objects.all().order_by("name")
        return StandardResponse(
            data=BrandAdminSerializer(brands, many=True).data,
            request=request,
        )

    @extend_schema(tags=["Admin — Brands"], summary="Create brand")
    def create(self, request):
        if err := self._require_superadmin(request):
            return err
        serializer = BrandAdminSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        brand = serializer.save()
        # Auto-seed BRAND_OWNER / MANAGER / CASHIER / KITCHEN roles for the new brand
        from apps.rbac.utils import seed_roles_for_brand
        seed_roles_for_brand(brand)
        return StandardResponse(
            data=BrandAdminSerializer(brand).data,
            message="Brand created.",
            request=request,
            status=http_status.HTTP_201_CREATED,
        )

    @extend_schema(tags=["Admin — Brands"], summary="Get brand detail")
    def retrieve(self, request, pk=None):
        if err := self._require_superadmin(request):
            return err
        brand = get_object_or_404(Brand, pk=pk)
        return StandardResponse(
            data=BrandAdminSerializer(brand).data,
            request=request,
        )

    @extend_schema(tags=["Admin — Brands"], summary="Update brand (full)")
    def update(self, request, pk=None):
        if err := self._require_superadmin(request):
            return err
        brand = get_object_or_404(Brand, pk=pk)
        serializer = BrandAdminSerializer(brand, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return StandardResponse(
            data=BrandAdminSerializer(brand).data,
            message="Brand updated.",
            request=request,
        )

    @extend_schema(tags=["Admin — Brands"], summary="Partial update brand")
    def partial_update(self, request, pk=None):
        if err := self._require_superadmin(request):
            return err
        brand = get_object_or_404(Brand, pk=pk)
        serializer = BrandAdminSerializer(brand, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return StandardResponse(
            data=BrandAdminSerializer(brand).data,
            message="Brand updated.",
            request=request,
        )

    @extend_schema(tags=["Admin — Brands"], summary="Delete brand and all related data")
    def destroy(self, request, pk=None):
        if err := self._require_superadmin(request):
            return err
        brand = get_object_or_404(Brand, pk=pk)

        with transaction.atomic():
            # 1. Payments (bergantung pada Order)
            from apps.payments.models import PaymentTransaction, ManualSettlement, MidtransWebhookLog
            order_ids = brand.orders.values_list("id", flat=True)
            PaymentTransaction.objects.filter(order_id__in=order_ids).delete()
            ManualSettlement.objects.filter(order_id__in=order_ids).delete()

            # 2. Order items & history
            from apps.orders.models import OrderItem, OrderStatusHistory
            OrderItem.objects.filter(order_id__in=order_ids).delete()
            OrderStatusHistory.objects.filter(order_id__in=order_ids).delete()

            # 3. Orders
            brand.orders.all().delete()

            # 4. OutletProduct & Promotion (bergantung pada BrandProduct dan Outlet)
            from apps.catalog.models import OutletProduct, Promotion, BrandProduct, Category
            bp_ids = brand.brand_products.values_list("id", flat=True)
            OutletProduct.objects.filter(brand_product_id__in=bp_ids).delete()
            Promotion.objects.filter(brand_product_id__in=bp_ids).delete()

            # 5. BrandProduct & Category
            brand.brand_products.all().delete()
            brand.categories.all().delete()

            # 6. Tables (bergantung pada Outlet)
            from apps.tables.models import Table
            Table.objects.filter(outlet__brand=brand).delete()

            # 7. Employees
            brand.employees.all().delete()

            # 8. Outlets
            brand.outlets.all().delete()

            # 9. Roles (CASCADE sudah handle RolePermission, tapi hapus eksplisit)
            brand.roles.all().delete()

            # 10. Brand itu sendiri
            brand.delete()

        return StandardResponse(
            message="Brand dan semua data terkait berhasil dihapus.",
            request=request,
            status=http_status.HTTP_204_NO_CONTENT,
        )

    @extend_schema(
        tags=["Admin — Brands"],
        summary="Create Brand Owner account",
        description="Creates an Employee with the BRAND_OWNER system role for the specified brand. SuperAdmin only.",
    )
    @action(detail=True, methods=["post"], url_path="create-owner")
    def create_owner(self, request, pk=None):
        if err := self._require_superadmin(request):
            return err

        brand = get_object_or_404(Brand, pk=pk)

        # Validate input
        class OwnerCreateSerializer(drf_serializers.Serializer):
            full_name = drf_serializers.CharField(max_length=150)
            email = drf_serializers.EmailField()
            password = drf_serializers.CharField(min_length=8, write_only=True)

        serializer = OwnerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from apps.staff.models import Employee
        from apps.rbac.models import Role
        from apps.rbac.utils import seed_roles_for_brand

        # Ensure system roles exist for this brand
        seed_roles_for_brand(brand)

        owner_role = Role.objects.filter(brand=brand, name="BRAND_OWNER").first()
        if not owner_role:
            return StandardResponse(
                success=False,
                code="INTERNAL_ERROR",
                message="BRAND_OWNER role could not be seeded for this brand.",
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request,
            )

        if Employee.objects.filter(brand=brand, email=data["email"]).exists():
            return StandardResponse(
                success=False,
                code="VALIDATION_ERROR",
                message=f"Email '{data['email']}' sudah terdaftar sebagai staff di brand ini.",
                status=http_status.HTTP_400_BAD_REQUEST,
                request=request,
            )

        employee = Employee(
            brand=brand,
            role=owner_role,
            email=data["email"],
            full_name=data["full_name"],
            outlet=None,
        )
        employee.set_password(data["password"])
        employee.save()

        return StandardResponse(
            data={
                "id": str(employee.id),
                "full_name": employee.full_name,
                "email": employee.email,
                "brand_id": str(brand.id),
                "brand_name": brand.name,
                "role": "BRAND_OWNER",
            },
            message=f"Akun owner berhasil dibuat untuk brand '{brand.name}'.",
            request=request,
            status=http_status.HTTP_201_CREATED,
        )


class BrandProfileViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permissions = {"me": None}  # PATCH permission checked inline

    @action(detail=False, methods=["get", "patch"], url_path="me")
    def me(self, request):
        brand = get_object_or_404(Brand, id=request.tenant["brand_id"])

        if request.method == "PATCH":
            serializer = BrandSerializer(
                brand, data=request.data, partial=True, context={"request": request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return StandardResponse(
                data=serializer.data,
                message="Brand profile updated.",
                request=request,
            )

        return StandardResponse(
            data=BrandSerializer(brand, context={"request": request}).data,
            request=request,
        )


@extend_schema_view(
    list=extend_schema(tags=["Outlets"], summary="List outlets"),
    retrieve=extend_schema(tags=["Outlets"], summary="Get outlet", responses={200: OutletSerializer, **COMMON_ERROR_RESPONSES}),
    create=extend_schema(tags=["Outlets"], summary="Create outlet", request=OutletCreateSerializer, responses={201: OutletSerializer, **COMMON_ERROR_RESPONSES}),
    update=extend_schema(tags=["Outlets"], summary="Update outlet", request=OutletCreateSerializer, responses={200: OutletSerializer, **COMMON_ERROR_RESPONSES}),
    partial_update=extend_schema(tags=["Outlets"], summary="Partial update outlet", request=OutletCreateSerializer, responses={200: OutletSerializer, **COMMON_ERROR_RESPONSES}),
    destroy=extend_schema(tags=["Outlets"], summary="Delete outlet", responses={204: None, **COMMON_ERROR_RESPONSES}),
)
class OutletViewSet(TenantScopedViewSet):
    serializer_class = OutletSerializer
    tenant_field = "brand"
    outlet_field = None

    required_permissions = {
        "list": "outlet.view",
        "retrieve": "outlet.view",
        "create": "outlet.create",
        "update": "outlet.update",
        "partial_update": "outlet.update",
        "destroy": "outlet.delete",
    }

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return Outlet.objects.none()
        return Outlet.objects.filter(brand_id=tenant["brand_id"]).order_by("name")

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return OutletCreateSerializer
        return OutletSerializer

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        return StandardResponse(data=OutletSerializer(qs, many=True).data, request=request)

    def create(self, request, *args, **kwargs):
        serializer = OutletCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        outlet = serializer.save(brand_id=request.tenant["brand_id"])
        return StandardResponse(
            data=OutletSerializer(outlet).data,
            message="Outlet created.",
            request=request,
            status=http_status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = OutletCreateSerializer(instance, data=request.data, partial=partial, context={"request": request})
        serializer.is_valid(raise_exception=True)
        outlet = serializer.save()
        return StandardResponse(
            data=OutletSerializer(outlet).data,
            message="Outlet updated.",
            request=request,
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return StandardResponse(message="Outlet deleted.", request=request, status=http_status.HTTP_204_NO_CONTENT)


class PublicBrandListView(APIView):
    """GET /api/v1/public/brands/ — List all active brands. No auth required."""

    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Public"],
        summary="List all active brands",
        description="Returns all active brands with public-facing info. No authentication required.",
        responses={200: PublicBrandSerializer(many=True)},
    )
    def get(self, request):
        brands = Brand.objects.filter(is_active=True).order_by("name")
        return StandardResponse(
            data=PublicBrandSerializer(brands, many=True).data,
            request=request,
        )


class PublicOutletListView(APIView):
    """GET /api/v1/public/outlets/?brand_id=<uuid> — List active outlets for a brand. No auth required."""

    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Public"],
        summary="List outlets by brand (no location required)",
        description="Returns all active outlets for a brand ordered by name. Use /api/v1/outlets/nearby/ instead if customer location is available.",
        parameters=[
            {"name": "brand_id", "in": "query", "required": True, "schema": {"type": "string", "format": "uuid"}},
        ],
        responses={200: PublicOutletSerializer(many=True)},
    )
    def get(self, request):
        brand_id = request.query_params.get("brand_id", "").strip()
        if not brand_id:
            return StandardResponse(
                success=False, code="VALIDATION_ERROR",
                message="Query param 'brand_id' wajib diisi.",
                status=400, request=request,
            )

        outlets = (
            Outlet.objects
            .filter(brand_id=brand_id, is_active=True)
            .order_by("name")
        )

        return StandardResponse(
            data=PublicOutletSerializer(outlets, many=True).data,
            request=request,
        )
