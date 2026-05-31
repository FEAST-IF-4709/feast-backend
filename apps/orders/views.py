from django.db import transaction
from django.db.models import Count
from django.utils.dateparse import parse_date
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter
from rest_framework import generics, serializers as drf_serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from core.permissions.has_permission import HasPermission
from core.responses.standard import StandardResponse
from core.schema import COMMON_ERROR_RESPONSES
from .models import Order, OrderItem, OrderStatusHistory
from .pagination import OrderCursorPagination
from .serializers import (
    OrderDetailSerializer,
    OrderListSerializer,
    OrderSerializer,
    OrderQRTableCreateSerializer,
    OrderCashierPOSCreateSerializer,
    compute_order_totals,
)


class OrderQRTableCreateView(APIView):
    """POST /api/v1/orders/qr-table/ — Customer self-order via QR table scan."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Orders"],
        summary="Create QR table order (customer)",
        description="Place a new order as an authenticated customer scanned from a table QR code.",
        request=OrderQRTableCreateSerializer,
        responses={
            201: inline_serializer("QRTableOrderCreated", fields={
                "order_id": drf_serializers.UUIDField(),
                "order_number": drf_serializers.CharField(),
                "grand_total": drf_serializers.DecimalField(max_digits=12, decimal_places=2),
                "valid_payment_methods": drf_serializers.ListField(child=drf_serializers.CharField()),
            }),
            **COMMON_ERROR_RESPONSES,
        },
    )
    def post(self, request):
        tenant = getattr(request, "tenant", None)
        if not tenant or tenant.get("actor_type") != "CUSTOMER":
            return StandardResponse(
                success=False, code="PERMISSION_DENIED",
                message="Only customers can place QR table orders.",
                status=403, request=request,
            )

        serializer = OrderQRTableCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        table = data["_table"]
        outlet = data["_outlet"]
        product_map = data["_product_map"]

        order_items_payload, subtotal, discount_total, grand_total = compute_order_totals(
            data["items"], product_map
        )

        with transaction.atomic():
            order = Order.objects.create(
                brand=outlet.brand,
                outlet=outlet,
                customer=request.user,
                table=table,
                order_source=Order.OrderSource.QR_TABLE,
                payment_status=Order.PaymentStatus.PENDING,
                fulfillment_status=Order.FulfillmentStatus.RECEIVED,
                subtotal=subtotal,
                discount_total=discount_total,
                grand_total=grand_total,
                notes=data.get("notes", ""),
            )
            OrderItem.objects.bulk_create([
                OrderItem(
                    order=order,
                    outlet_product=item["outlet_product"],
                    product_snapshot=item["product_snapshot"],
                    quantity=item["quantity"],
                    unit_price=item["unit_price"],
                    line_total=item["line_total"],
                    item_notes=item.get("item_notes", ""),
                )
                for item in order_items_payload
            ])
            OrderStatusHistory.objects.create(
                order=order,
                from_status=None,
                to_status=Order.FulfillmentStatus.RECEIVED,
            )

        response_data = {
            "order_id": str(order.id),
            "order_number": order.order_number,
            "grand_total": str(order.grand_total),
            "valid_payment_methods": [
                Order.PaymentMethod.QRIS_MIDTRANS,
                Order.PaymentMethod.BANK_TRANSFER_MIDTRANS,
            ],
        }

        return StandardResponse(
            data=response_data,
            message="Order created successfully.",
            status=201,
            request=request,
        )


class OrderCashierPOSCreateView(APIView):
    """POST /api/v1/orders/cashier-pos/ — Cashier POS order."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Orders"],
        summary="Create cashier POS order",
        description="Place an order from the cashier POS terminal. Requires `cashier.order.create` permission.",
        request=OrderCashierPOSCreateSerializer,
        responses={201: OrderSerializer, **COMMON_ERROR_RESPONSES},
    )
    def post(self, request):
        tenant = getattr(request, "tenant", None)
        if not tenant or tenant.get("actor_type") != "EMPLOYEE":
            return StandardResponse(
                success=False, code="PERMISSION_DENIED",
                message="Only employees can place cashier POS orders.",
                status=403, request=request,
            )

        if "cashier.order.create" not in tenant.get("permissions", frozenset()):
            return StandardResponse(
                success=False, code="PERMISSION_DENIED",
                message="Missing permission: cashier.order.create",
                status=403, request=request,
            )

        serializer = OrderCashierPOSCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        outlet = data["_outlet"]
        product_map = data["_product_map"]

        order_items_payload, subtotal, discount_total, grand_total = compute_order_totals(
            data["items"], product_map
        )

        customer_id = data.get("customer_id")
        table_id = data.get("table_id")

        with transaction.atomic():
            order = Order.objects.create(
                brand=outlet.brand,
                outlet=outlet,
                customer_id=customer_id,
                table_id=table_id,
                cashier_employee=request.user,
                order_source=Order.OrderSource.CASHIER_POS,
                walk_in_name=data.get("walk_in_name", ""),
                payment_method=data["payment_method"],
                payment_status=Order.PaymentStatus.PENDING,
                fulfillment_status=Order.FulfillmentStatus.RECEIVED,
                subtotal=subtotal,
                discount_total=discount_total,
                grand_total=grand_total,
                notes=data.get("notes", ""),
            )
            OrderItem.objects.bulk_create([
                OrderItem(
                    order=order,
                    outlet_product=item["outlet_product"],
                    product_snapshot=item["product_snapshot"],
                    quantity=item["quantity"],
                    unit_price=item["unit_price"],
                    line_total=item["line_total"],
                    item_notes=item.get("item_notes", ""),
                )
                for item in order_items_payload
            ])
            OrderStatusHistory.objects.create(
                order=order,
                from_status=None,
                to_status=Order.FulfillmentStatus.RECEIVED,
            )

        return StandardResponse(
            data=OrderSerializer(order).data,
            message="Order created successfully.",
            status=201,
            request=request,
        )


class CustomerOrderListView(APIView):
    """GET /api/v1/me/orders/ — Customer's own order history."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Orders"],
        summary="List customer order history",
        description="Returns all orders placed by the authenticated customer, newest first.",
        responses={200: OrderSerializer(many=True), **COMMON_ERROR_RESPONSES},
    )
    def get(self, request):
        tenant = getattr(request, "tenant", None)
        if not tenant or tenant.get("actor_type") != "CUSTOMER":
            return StandardResponse(
                success=False, code="PERMISSION_DENIED",
                message="Only customers can access their order history.",
                status=403, request=request,
            )

        qs = (
            Order.objects.filter(customer=request.user)
            .select_related("outlet__brand", "table")
            .prefetch_related("items")
            .order_by("-placed_at")
        )
        return StandardResponse(data=OrderSerializer(qs, many=True).data, request=request)


class OrderDetailView(APIView):
    """GET /api/v1/orders/{pk}/ — Owner customer OR employee at same brand/outlet."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Orders"],
        summary="Get order details",
        description="Retrieve full order details including items and status history. Accessible by the order's customer or any employee in the same brand/outlet.",
        responses={200: OrderDetailSerializer, **COMMON_ERROR_RESPONSES},
    )
    def get(self, request, pk):
        tenant = getattr(request, "tenant", None)
        actor_type = (tenant or {}).get("actor_type")

        if actor_type == "CUSTOMER":
            qs = Order.objects.filter(pk=pk, customer=request.user)
        elif actor_type == "EMPLOYEE":
            qs = Order.objects.filter(
                pk=pk,
                brand_id=tenant["brand_id"],
                outlet_id__in=tenant["outlet_ids"],
            )
        else:
            qs = Order.objects.none()

        order = (
            qs.select_related("outlet__brand", "table", "customer", "cashier_employee")
              .prefetch_related("items", "status_history")
              .first()
        )
        if not order:
            return StandardResponse(
                success=False, code="NOT_FOUND",
                message="Order tidak ditemukan.",
                status=404, request=request,
            )

        return StandardResponse(data=OrderDetailSerializer(order).data, request=request)


@extend_schema(
    tags=["Orders"],
    summary="List orders",
    description=(
        "Returns all orders for the authenticated staff's outlet(s), ordered by most recent first. "
        "Supports filtering by date range, fulfillment/payment status, outlet, and order number. "
        "Requires `orders.view` permission. Paginated via cursor (default 25 per page, max 100)."
    ),
    parameters=[
        OpenApiParameter("date_from", str, description="Start date filter. Format: YYYY-MM-DD."),
        OpenApiParameter("date_to", str, description="End date filter. Format: YYYY-MM-DD."),
        OpenApiParameter("fulfillment_status", str, description="Comma-separated fulfillment statuses, e.g. RECEIVED,COMPLETED,CANCELLED."),
        OpenApiParameter("payment_status", str, description="Comma-separated payment statuses, e.g. SETTLED,REFUNDED."),
        OpenApiParameter("outlet_id", str, description="Filter by specific outlet UUID. Must be one of the tenant's accessible outlets."),
        OpenApiParameter("order_number", str, description="Partial match on order number (case-insensitive)."),
        OpenApiParameter("cursor", str, description="Opaque cursor for next/previous page navigation."),
        OpenApiParameter("page_size", int, description="Items per page. Range: 1–100. Default: 25."),
    ],
    responses={200: OrderListSerializer(many=True), **COMMON_ERROR_RESPONSES},
)
class OrderListView(generics.ListAPIView):
    """GET /api/v1/orders/ — Paginated order history for staff dashboard."""

    action = "list"  # required: HasPermission reads view.action; ListAPIView doesn't set it
    serializer_class = OrderListSerializer
    permission_classes = [IsAuthenticated, HasPermission]
    required_permissions = {"list": "orders.view"}
    pagination_class = OrderCursorPagination

    def get_queryset(self):
        tenant = self.request.tenant
        qs = Order.objects.filter(
            brand_id=tenant["brand_id"],
            outlet_id__in=tenant["outlet_ids"],
        )
        qs = self._apply_filters(qs)
        return (
            qs.select_related("outlet", "customer", "table", "cashier_employee")
              .annotate(items_count=Count("items"))
              .order_by("-placed_at")
        )

    def _apply_filters(self, qs):
        params = self.request.query_params

        if date_from := params.get("date_from"):
            parsed = parse_date(date_from)
            if not parsed:
                raise ValidationError({"date_from": "Invalid date format. Use YYYY-MM-DD."})
            qs = qs.filter(placed_at__date__gte=parsed)

        if date_to := params.get("date_to"):
            parsed = parse_date(date_to)
            if not parsed:
                raise ValidationError({"date_to": "Invalid date format. Use YYYY-MM-DD."})
            qs = qs.filter(placed_at__date__lte=parsed)

        if fulfillment := params.get("fulfillment_status"):
            valid = set(Order.FulfillmentStatus.values)
            statuses = [s.strip().upper() for s in fulfillment.split(",") if s.strip()]
            statuses = [s for s in statuses if s in valid]
            if statuses:
                qs = qs.filter(fulfillment_status__in=statuses)

        if payment := params.get("payment_status"):
            valid = set(Order.PaymentStatus.values)
            statuses = [s.strip().upper() for s in payment.split(",") if s.strip()]
            statuses = [s for s in statuses if s in valid]
            if statuses:
                qs = qs.filter(payment_status__in=statuses)

        if outlet_id := params.get("outlet_id"):
            allowed = [str(o) for o in self.request.tenant["outlet_ids"]]
            if outlet_id not in allowed:
                raise PermissionDenied("Outlet not accessible.")
            qs = qs.filter(outlet_id=outlet_id)

        if order_number := params.get("order_number"):
            qs = qs.filter(order_number__icontains=order_number)

        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return StandardResponse(
                data=serializer.data,
                meta={
                    "next": self.paginator.get_next_link(),
                    "previous": self.paginator.get_previous_link(),
                },
                request=request,
            )
        serializer = self.get_serializer(queryset, many=True)
        return StandardResponse(data=serializer.data, request=request)
