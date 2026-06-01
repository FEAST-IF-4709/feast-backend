from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status as http_status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from core.permissions.has_permission import HasPermission
from core.responses.standard import StandardResponse
from core.viewsets.tenant_scoped import TenantScopedViewSet
from core.schema import COMMON_ERROR_RESPONSES
from drf_spectacular.utils import extend_schema, extend_schema_view
from .models import Brand, Outlet
from .serializers import BrandSerializer, OutletSerializer, OutletCreateSerializer


class BrandProfileViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permissions = {"me": None}  # PATCH permission checked inline

    @action(detail=False, methods=["get", "patch"], url_path="me")
    def me(self, request):
        brand = get_object_or_404(Brand, id=request.tenant["brand_id"])

        if request.method == "PATCH":
            if "brand.update" not in request.tenant.get("permissions", frozenset()):
                return StandardResponse(
                    success=False,
                    code="FORBIDDEN",
                    message="You do not have brand.update permission.",
                    status=403,
                    request=request,
                )
            serializer = BrandSerializer(brand, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return StandardResponse(
                data=serializer.data,
                message="Brand profile updated.",
                request=request,
            )

        return StandardResponse(data=BrandSerializer(brand).data, request=request)


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
