from django.db import transaction
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from core.responses.standard import StandardResponse
from .models import Order, OrderItem, OrderStatusHistory
from .serializers import (
    OrderSerializer,
    OrderQRTableCreateSerializer,
    OrderCashierPOSCreateSerializer,
    compute_order_totals,
)


class OrderQRTableCreateView(APIView):
    """POST /api/v1/orders/qr-table/ — Customer self-order via QR table scan."""

    permission_classes = [IsAuthenticated]

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
