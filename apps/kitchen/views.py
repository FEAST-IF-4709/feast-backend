from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from core.responses.standard import StandardResponse
from core.schema import COMMON_ERROR_RESPONSES
from apps.orders.models import Order
from .serializers import KitchenOrderSerializer, KitchenStatusUpdateSerializer


def _require_employee_permission(request, codename):
    tenant = getattr(request, "tenant", None)
    if not tenant or tenant.get("actor_type") != "EMPLOYEE":
        return False
    return codename in tenant.get("permissions", frozenset())


class KitchenOrderListView(APIView):
    """GET /api/v1/kitchen/orders/"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Kitchen"],
        summary="List kitchen orders",
        description="Returns settled orders for the authenticated staff's outlet(s), filtered by fulfillment status. Requires `kitchen.order.view` permission.",
        parameters=[
            OpenApiParameter("status", str, description="Comma-separated fulfillment statuses. Default: RECEIVED,IN_PROGRESS,READY"),
            OpenApiParameter("since", str, description="ISO 8601 datetime — only return orders placed after this timestamp"),
            OpenApiParameter("limit", int, description="Max orders to return. Default: 100"),
        ],
        responses={200: KitchenOrderSerializer(many=True), **COMMON_ERROR_RESPONSES},
    )
    def get(self, request):
        if not _require_employee_permission(request, "kitchen.order.view"):
            return StandardResponse(
                success=False, code="PERMISSION_DENIED",
                message="Missing permission: kitchen.order.view",
                status=403, request=request,
            )

        tenant = request.tenant
        raw_statuses = request.query_params.get("status", "RECEIVED,IN_PROGRESS,READY")
        requested_statuses = [s.strip() for s in raw_statuses.split(",")]

        valid_statuses = [
            Order.FulfillmentStatus.RECEIVED,
            Order.FulfillmentStatus.IN_PROGRESS,
            Order.FulfillmentStatus.READY,
        ]
        filtered_statuses = [s for s in requested_statuses if s in valid_statuses] or valid_statuses

        qs = Order.objects.filter(
            brand_id=tenant["brand_id"],
            outlet_id__in=tenant["outlet_ids"],
            payment_status=Order.PaymentStatus.SETTLED,
            fulfillment_status__in=filtered_statuses,
        ).select_related("table", "customer", "cashier_employee").prefetch_related(
            "items__outlet_product__brand_product__category"
        ).order_by("placed_at")

        since = request.query_params.get("since")
        if since:
            from django.utils.dateparse import parse_datetime
            since_dt = parse_datetime(since)
            if since_dt:
                qs = qs.filter(placed_at__gte=since_dt)

        try:
            limit = int(request.query_params.get("limit", 100))
        except (ValueError, TypeError):
            limit = 100

        qs = qs[:limit]

        return StandardResponse(
            data=KitchenOrderSerializer(qs, many=True).data,
            request=request,
        )


class KitchenOrderStatusUpdateView(APIView):
    """PATCH /api/v1/kitchen/orders/{pk}/status/"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Kitchen"],
        summary="Update order fulfillment status",
        description="Advances an order through the fulfillment state machine. Broadcasts the change via WebSocket. Requires `kitchen.order.update_status` permission.",
        request=KitchenStatusUpdateSerializer,
        responses={200: KitchenOrderSerializer, **COMMON_ERROR_RESPONSES, 409: None},
    )
    def patch(self, request, pk):
        if not _require_employee_permission(request, "kitchen.order.update_status"):
            return StandardResponse(
                success=False, code="PERMISSION_DENIED",
                message="Missing permission: kitchen.order.update_status",
                status=403, request=request,
            )

        tenant = request.tenant
        try:
            order = Order.objects.get(
                pk=pk,
                brand_id=tenant["brand_id"],
                outlet_id__in=tenant["outlet_ids"],
            )
        except Order.DoesNotExist:
            return StandardResponse(
                success=False, code="NOT_FOUND",
                message="Order not found.", status=404, request=request,
            )

        if order.payment_status != Order.PaymentStatus.SETTLED:
            return StandardResponse(
                success=False, code="VALIDATION_ERROR",
                message="Only settled orders can have their fulfillment status updated.",
                status=400, request=request,
            )

        serializer = KitchenStatusUpdateSerializer(
            data=request.data, context={"request": request, "order": order}
        )
        serializer.is_valid(raise_exception=True)

        to_status = serializer.validated_data["to_status"]
        notes = serializer.validated_data.get("notes")

        with transaction.atomic():
            order_locked = Order.objects.select_for_update().get(pk=pk)
            try:
                order_locked.apply_fulfillment_transition(
                    to_status,
                    changed_by=request.user,
                    notes=notes,
                    actor_permissions=tenant["permissions"],
                )
            except DjangoValidationError as exc:
                return StandardResponse(
                    success=False, code="STATE_TRANSITION_INVALID",
                    message=exc.message if hasattr(exc, "message") else str(exc),
                    status=409, request=request,
                )
            except DjangoPermissionDenied as exc:
                return StandardResponse(
                    success=False, code="PERMISSION_DENIED",
                    message=str(exc), status=403, request=request,
                )

            _outlet_id = str(order_locked.outlet_id)
            _order_id = str(order_locked.id)
            _to_status = to_status
            transaction.on_commit(
                lambda: _broadcast_status_change(_outlet_id, _order_id, _to_status)
            )

        return StandardResponse(
            data=KitchenOrderSerializer(order_locked).data,
            message="Order status updated.",
            request=request,
        )


class KitchenOrderCancelView(APIView):
    """POST /api/v1/kitchen/orders/{pk}/cancel/"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Kitchen"],
        summary="Force cancel order",
        description="Cancels a settled order regardless of its current fulfillment state. Requires `kitchen.order.force_cancel` permission.",
        responses={200: KitchenOrderSerializer, **COMMON_ERROR_RESPONSES, 409: None},
    )
    def post(self, request, pk):
        if not _require_employee_permission(request, "kitchen.order.force_cancel"):
            return StandardResponse(
                success=False, code="PERMISSION_DENIED",
                message="Missing permission: kitchen.order.force_cancel",
                status=403, request=request,
            )

        tenant = request.tenant
        try:
            order = Order.objects.get(
                pk=pk,
                brand_id=tenant["brand_id"],
                outlet_id__in=tenant["outlet_ids"],
            )
        except Order.DoesNotExist:
            return StandardResponse(
                success=False, code="NOT_FOUND",
                message="Order not found.", status=404, request=request,
            )

        cancel_reason = request.data.get("cancel_reason", "").strip()
        if not cancel_reason:
            return StandardResponse(
                success=False, code="VALIDATION_ERROR",
                message="Cancel reason (cancel_reason) is required.",
                status=400, request=request,
            )

        with transaction.atomic():
            order_locked = Order.objects.select_for_update().get(pk=pk)
            try:
                order_locked.apply_fulfillment_transition(
                    Order.FulfillmentStatus.CANCELLED,
                    changed_by=request.user,
                    notes=cancel_reason,
                    actor_permissions=tenant["permissions"],
                )
            except DjangoValidationError as exc:
                return StandardResponse(
                    success=False, code="STATE_TRANSITION_INVALID",
                    message=exc.message if hasattr(exc, "message") else str(exc),
                    status=409, request=request,
                )

            _outlet_id = str(order_locked.outlet_id)
            _order_id = str(order_locked.id)
            transaction.on_commit(
                lambda: _broadcast_cancel(_outlet_id, _order_id)
            )

        return StandardResponse(
            data=KitchenOrderSerializer(order_locked).data,
            message="Order cancelled.",
            request=request,
        )


def _broadcast_status_change(outlet_id, order_id_str, to_status):
    from apps.realtime.broadcast import broadcast_to_kitchen, broadcast_to_order, broadcast_to_dashboard
    thin = {"order_id": order_id_str, "fulfillment_status": to_status}
    broadcast_to_kitchen(outlet_id, "order.status_changed", thin)
    broadcast_to_dashboard(outlet_id, "order.status_changed", thin)
    broadcast_to_order(order_id_str, "fulfillment.status_changed", {"fulfillment_status": to_status})


def _broadcast_cancel(outlet_id, order_id_str):
    from apps.realtime.broadcast import broadcast_to_kitchen, broadcast_to_order, broadcast_to_dashboard
    thin = {"order_id": order_id_str, "fulfillment_status": Order.FulfillmentStatus.CANCELLED}
    broadcast_to_kitchen(outlet_id, "order.cancelled", thin)
    broadcast_to_dashboard(outlet_id, "order.cancelled", thin)
    broadcast_to_order(
        order_id_str,
        "fulfillment.status_changed",
        {"fulfillment_status": Order.FulfillmentStatus.CANCELLED},
    )
