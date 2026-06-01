from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from core.responses.standard import StandardResponse
from core.schema import COMMON_ERROR_RESPONSES
from apps.orders.models import Order
from apps.orders.serializers import OrderSerializer
from .models import PaymentTransaction, MidtransWebhookLog, ManualSettlement
from .serializers import (
    InitiateQRISSerializer,
    ManualSettleSerializer,
    ManualSettlementSerializer,
)
from .services.midtrans import MidtransClient, MidtransError


class InitiateQRISView(APIView):
    """POST /api/v1/payments/initiate-qris/"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Payments"],
        summary="Initiate QRIS payment",
        description="Create a QRIS payment transaction via Midtrans. Returns QR string and image URL. If an active transaction already exists for the order, it is returned instead.",
        request=InitiateQRISSerializer,
        responses={
            200: inline_serializer("QRISResponse", fields={
                "transaction_id": drf_serializers.CharField(),
                "qr_string": drf_serializers.CharField(),
                "qr_image_url": drf_serializers.URLField(),
                "expires_at": drf_serializers.DateTimeField(),
                "amount": drf_serializers.DecimalField(max_digits=12, decimal_places=2),
                "polling_endpoint": drf_serializers.CharField(),
                "websocket_topic": drf_serializers.CharField(),
            }),
            201: inline_serializer("QRISResponseCreated", fields={
                "transaction_id": drf_serializers.CharField(),
                "qr_string": drf_serializers.CharField(),
                "qr_image_url": drf_serializers.URLField(),
                "expires_at": drf_serializers.DateTimeField(),
                "amount": drf_serializers.DecimalField(max_digits=12, decimal_places=2),
                "polling_endpoint": drf_serializers.CharField(),
                "websocket_topic": drf_serializers.CharField(),
            }),
            **COMMON_ERROR_RESPONSES,
            502: None,
        },
    )
    def post(self, request):
        serializer = InitiateQRISSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        order = serializer._order

        existing = PaymentTransaction.objects.filter(
            order=order, expires_at__gt=timezone.now()
        ).first()
        if existing:
            return StandardResponse(
                data=self._build_response(existing, order),
                message="Existing active payment transaction returned.",
                request=request,
            )

        client = MidtransClient()
        try:
            result = client.charge_qris(order)
        except MidtransError as exc:
            return StandardResponse(
                success=False,
                code="PAYMENT_GATEWAY_ERROR",
                message=str(exc),
                status=502,
                request=request,
            )

        pt = PaymentTransaction.objects.create(
            order=order,
            midtrans_order_id=order.order_number,
            transaction_id=result["transaction_id"],
            payment_type="qris",
            gross_amount=order.grand_total,
            qr_string=result["qr_string"],
            qr_image_url=result["qr_image_url"],
            expires_at=result["expires_at"],
            transaction_status="pending",
            raw_request_payload=result["raw_request_payload"],
            raw_response_payload=result["raw_response_payload"],
        )

        return StandardResponse(
            data=self._build_response(pt, order),
            message="Payment initiated.",
            status=201,
            request=request,
        )

    def _build_response(self, pt, order):
        return {
            "transaction_id": pt.transaction_id,
            "qr_string": pt.qr_string,
            "qr_image_url": pt.qr_image_url,
            "expires_at": pt.expires_at,
            "amount": str(pt.gross_amount),
            "polling_endpoint": f"/api/v1/payments/{order.id}/status/",
            "websocket_topic": f"order.{order.id}",
        }


class MidtransWebhookView(APIView):
    """POST /api/v1/payments/webhook/midtrans/ — public, signature-verified."""

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Payments"],
        summary="Midtrans payment webhook",
        description="Receives payment status notifications from Midtrans. Verifies signature before processing. Idempotent — duplicate events are ignored.",
        responses={200: None, 403: None},
    )
    def post(self, request):
        payload = request.data

        order_id = payload.get("order_id", "")
        status_code = payload.get("status_code", "")
        gross_amount = payload.get("gross_amount", "")
        signature_key = payload.get("signature_key", "")
        transaction_status = payload.get("transaction_status", "")
        transaction_time = payload.get("transaction_time", "")

        sig_valid = MidtransClient().verify_signature(order_id, status_code, gross_amount, signature_key)

        if not sig_valid:
            MidtransWebhookLog.objects.create(
                midtrans_order_id=order_id,
                transaction_status=transaction_status,
                signature_valid=False,
                payload=payload,
                processing_result=MidtransWebhookLog.ProcessingResult.REJECTED_INVALID_SIG,
            )
            return StandardResponse(
                success=False, code="WEBHOOK_SIGNATURE_INVALID",
                message="Invalid signature.", status=403, request=request,
            )

        duplicate = MidtransWebhookLog.objects.filter(
            midtrans_order_id=order_id,
            transaction_status=transaction_status,
            payload__transaction_time=transaction_time,
            processing_result=MidtransWebhookLog.ProcessingResult.APPLIED,
        ).exists()

        if duplicate:
            MidtransWebhookLog.objects.create(
                midtrans_order_id=order_id,
                transaction_status=transaction_status,
                signature_valid=True,
                payload=payload,
                processing_result=MidtransWebhookLog.ProcessingResult.IGNORED_DUPLICATE,
            )
            return StandardResponse(message="Duplicate event ignored.", request=request)

        try:
            with transaction.atomic():
                order = (
                    Order.objects.select_for_update()
                    .select_related("outlet")
                    .get(order_number=order_id)
                )

                # REFUNDED dan EXPIRED adalah terminal absolut — tidak boleh ditimpa apapun
                if order.payment_status in (Order.PaymentStatus.REFUNDED, Order.PaymentStatus.EXPIRED):
                    MidtransWebhookLog.objects.create(
                        midtrans_order_id=order_id,
                        transaction_status=transaction_status,
                        signature_valid=True,
                        payload=payload,
                        processing_result=MidtransWebhookLog.ProcessingResult.IGNORED_OUT_OF_ORDER,
                    )
                    return StandardResponse(message="Out-of-order event ignored.", request=request)

                # SETTLED hanya boleh diikuti "refund"
                if (
                    order.payment_status == Order.PaymentStatus.SETTLED
                    and transaction_status != "refund"
                ):
                    MidtransWebhookLog.objects.create(
                        midtrans_order_id=order_id,
                        transaction_status=transaction_status,
                        signature_valid=True,
                        payload=payload,
                        processing_result=MidtransWebhookLog.ProcessingResult.IGNORED_OUT_OF_ORDER,
                    )
                    return StandardResponse(message="Out-of-order event ignored.", request=request)

                _GATEWAY_REJECTIONS = {"deny", "cancel"}

                if transaction_status in _GATEWAY_REJECTIONS:
                    # Catat penolakan gateway — JANGAN ubah order.payment_status agar customer bisa retry
                    PaymentTransaction.objects.filter(order=order).update(
                        transaction_status=transaction_status,
                        last_webhook_payload=payload,
                    )
                    MidtransWebhookLog.objects.create(
                        midtrans_order_id=order_id,
                        transaction_status=transaction_status,
                        signature_valid=True,
                        payload=payload,
                        processing_result=MidtransWebhookLog.ProcessingResult.APPLIED,
                    )
                else:
                    status_map = {
                        "settlement": Order.PaymentStatus.SETTLED,
                        "expire": Order.PaymentStatus.EXPIRED,
                        "refund": Order.PaymentStatus.REFUNDED,
                    }
                    new_payment_status = status_map.get(transaction_status)
                    if new_payment_status:
                        order.payment_status = new_payment_status
                        order.save(update_fields=["payment_status"])

                    PaymentTransaction.objects.filter(order=order).update(
                        transaction_status=transaction_status,
                        last_webhook_payload=payload,
                    )
                    MidtransWebhookLog.objects.create(
                        midtrans_order_id=order_id,
                        transaction_status=transaction_status,
                        signature_valid=True,
                        payload=payload,
                        processing_result=MidtransWebhookLog.ProcessingResult.APPLIED,
                    )

                    if transaction_status == "settlement":
                        _outlet_id = str(order.outlet_id)
                        _order_id = str(order.id)
                        transaction.on_commit(
                            lambda: _broadcast_settled(_outlet_id, _order_id)
                        )

        except Order.DoesNotExist:
            pass

        return StandardResponse(message="Webhook processed.", request=request)


def _broadcast_settled(outlet_id, order_id_str):
    from apps.realtime.broadcast import broadcast_to_kitchen, broadcast_to_order, broadcast_to_dashboard
    thin = {"order_id": order_id_str, "outlet_id": outlet_id}
    broadcast_to_kitchen(outlet_id, "order.created", thin)
    broadcast_to_dashboard(outlet_id, "order.created", thin)
    broadcast_to_order(order_id_str, "payment.status_changed", {"payment_status": "SETTLED"})


class ManualSettleView(APIView):
    """POST /api/v1/payments/manual-settle/ — cashier confirms CASH/EDC."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Payments"],
        summary="Manually settle cash/EDC payment",
        description="Cashier confirms payment received in cash or via EDC. Marks the order as SETTLED and triggers kitchen broadcast. Requires `cashier.payment.settle_manual` permission.",
        request=ManualSettleSerializer,
        responses={201: ManualSettlementSerializer, **COMMON_ERROR_RESPONSES, 409: None},
    )
    def post(self, request):
        tenant = getattr(request, "tenant", None)
        if not tenant or tenant.get("actor_type") != "EMPLOYEE":
            return StandardResponse(
                success=False, code="PERMISSION_DENIED",
                message="Only employees can manually settle orders.",
                status=403, request=request,
            )

        if "cashier.payment.settle_manual" not in tenant.get("permissions", frozenset()):
            return StandardResponse(
                success=False, code="PERMISSION_DENIED",
                message="Missing permission: cashier.payment.settle_manual",
                status=403, request=request,
            )

        serializer = ManualSettleSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        order = data["_order"]

        with transaction.atomic():
            order_locked = Order.objects.select_for_update().get(pk=order.pk)

            if order_locked.payment_status != Order.PaymentStatus.PENDING:
                return StandardResponse(
                    success=False, code="PAYMENT_ALREADY_SETTLED",
                    message="Order payment is no longer pending.",
                    status=409, request=request,
                )

            settlement = ManualSettlement.objects.create(
                order=order_locked,
                cashier_employee=request.user,
                payment_method=data["payment_method"],
                amount_received=data["amount_received"],
                change_given=data["change_given"],
                edc_reference=data.get("edc_reference"),
            )
            order_locked.payment_status = Order.PaymentStatus.SETTLED
            order_locked.save(update_fields=["payment_status"])

            _outlet_id = str(order_locked.outlet_id)
            _order_id = str(order_locked.id)
            transaction.on_commit(
                lambda: _broadcast_settled(_outlet_id, _order_id)
            )

        return StandardResponse(
            data={
                "settlement": ManualSettlementSerializer(settlement).data,
                "order": OrderSerializer(order_locked).data,
            },
            message="Payment settled.",
            status=201,
            request=request,
        )


class PaymentStatusView(APIView):
    """GET /api/v1/payments/{order_id}/status/ — polling fallback."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Payments"],
        summary="Get payment status (polling fallback)",
        description="Poll the current payment and fulfillment status of an order. Prefer WebSocket subscription on `order.{id}` topic for real-time updates.",
        responses={
            200: inline_serializer("PaymentStatus", fields={
                "order_id": drf_serializers.UUIDField(),
                "payment_status": drf_serializers.CharField(),
                "fulfillment_status": drf_serializers.CharField(),
                "expires_at": drf_serializers.DateTimeField(allow_null=True),
            }),
            **COMMON_ERROR_RESPONSES,
        },
    )
    def get(self, request, order_id):
        tenant = getattr(request, "tenant", None)
        actor_type = (tenant or {}).get("actor_type")

        if actor_type == "CUSTOMER":
            qs = Order.objects.filter(pk=order_id, customer=request.user)
        elif actor_type == "EMPLOYEE":
            emp_filter = {"pk": order_id, "brand_id": tenant["brand_id"]}
            if tenant["outlet_ids"]:
                emp_filter["outlet_id__in"] = tenant["outlet_ids"]
            qs = Order.objects.filter(**emp_filter)
        else:
            qs = Order.objects.none()

        order = qs.first()
        if not order:
            return StandardResponse(
                success=False, code="NOT_FOUND",
                message="Order not found.", status=404, request=request,
            )

        data = {
            "order_id": str(order.id),
            "payment_status": order.payment_status,
            "fulfillment_status": order.fulfillment_status,
            "expires_at": None,
        }
        try:
            data["expires_at"] = order.payment_transaction.expires_at
        except PaymentTransaction.DoesNotExist:
            pass

        return StandardResponse(data=data, request=request)
