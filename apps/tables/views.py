from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from core.responses.standard import StandardResponse
from core.viewsets.tenant_scoped import TenantScopedViewSet
from apps.catalog.models import OutletProduct
from .models import Table
from .serializers import (
    TableSerializer,
    TableCreateSerializer,
    PublicTableResolveSerializer,
    PublicMenuProductSerializer,
)


class TableResolveThrottle(AnonRateThrottle):
    rate = "30/min"
    scope = "table_resolve"


class TableViewSet(TenantScopedViewSet):
    """
    CRUD for tables scoped to outlet (and brand via outlet FK).
    URL: /api/v1/outlets/{outlet_id}/tables/  and  /api/v1/tables/{id}/
    """

    serializer_class = TableSerializer
    tenant_field = "outlet"
    outlet_field = None

    required_permissions = {
        "list": "tables.view",
        "retrieve": "tables.view",
        "create": "tables.create",
        "update": "tables.update",
        "partial_update": "tables.update",
        "destroy": "tables.delete",
        "rotate_qr": "tables.update",
    }

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return Table.objects.none()

        qs = Table.objects.select_related("outlet__brand").filter(
            outlet__brand_id=tenant["brand_id"],
            outlet_id__in=tenant["outlet_ids"],
        )

        if outlet_id := self.kwargs.get("outlet_id"):
            qs = qs.filter(outlet_id=outlet_id)

        return qs

    def perform_create(self, serializer):
        outlet_id = self.kwargs.get("outlet_id")
        tenant = self.request.tenant
        if not outlet_id and len(tenant["outlet_ids"]) == 1:
            outlet_id = tenant["outlet_ids"][0]
        serializer.save(outlet_id=outlet_id)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return TableCreateSerializer
        return TableSerializer

    @action(detail=True, methods=["post"], url_path="rotate-qr")
    def rotate_qr(self, request, pk=None, **kwargs):
        table = self.get_object()
        table.rotate_qr()
        return StandardResponse(
            data=TableSerializer(table).data,
            message="QR token rotated.",
            request=request,
        )


class PublicTableResolveView(APIView):
    """GET /api/v1/public/tables/resolve/?token={qr_token}"""

    permission_classes = [AllowAny]
    throttle_classes = [TableResolveThrottle]

    def get(self, request):
        token = request.query_params.get("token", "").strip()
        if not token:
            return StandardResponse(
                success=False, code="VALIDATION_ERROR",
                message="token query parameter is required.",
                status=400, request=request,
            )

        try:
            table = Table.objects.select_related("outlet__brand").get(
                qr_token=token, is_active=True
            )
        except Table.DoesNotExist:
            return StandardResponse(
                success=False, code="NOT_FOUND",
                message="Table not found.", status=404, request=request,
            )

        if not table.outlet.is_active:
            return StandardResponse(
                success=False, code="OUTLET_INACTIVE",
                message="This outlet is currently inactive.",
                status=410, request=request,
            )

        return StandardResponse(
            data=PublicTableResolveSerializer(table).data,
            request=request,
        )


class PublicOutletMenuView(APIView):
    """GET /api/v1/public/outlets/{outlet_id}/menu/"""

    permission_classes = [AllowAny]

    def get(self, request, outlet_id):
        from apps.tenants.models import Outlet
        try:
            outlet = Outlet.objects.get(pk=outlet_id, is_active=True)
        except Outlet.DoesNotExist:
            return StandardResponse(
                success=False, code="NOT_FOUND",
                message="Outlet not found or inactive.", status=404, request=request,
            )

        products = (
            OutletProduct.objects.filter(outlet=outlet, stock_available=True)
            .select_related("brand_product__category", "brand_product__brand")
            .order_by("brand_product__category__name", "brand_product__name")
        )

        serialized = PublicMenuProductSerializer(products, many=True)

        grouped = {}
        for item in serialized.data:
            cat_id = str(item["category_id"])
            cat_name = item["category_name"]
            if cat_id not in grouped:
                grouped[cat_id] = {"category_id": cat_id, "category_name": cat_name, "items": []}
            grouped[cat_id]["items"].append(item)

        return StandardResponse(
            data={"outlet_id": str(outlet_id), "menu": list(grouped.values())},
            request=request,
        )
