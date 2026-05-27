import hashlib
import hmac
from datetime import timedelta

import requests as http_requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from core.responses.standard import StandardResponse
from apps.orders.models import Order
from apps.orders.serializers import OrderSerializer
from .models import PaymentTransaction, MidtransWebhookLog, ManualSettlement
from .serializers import (
    InitiateQRISSerializer,
    ManualSettleSerializer,
    ManualSettlementSerializer,
)


def _verify_midtrans_signature(order_id, status_code, gross_amount, signature_key):
    server_key = getattr(settings, "MIDTRANS_SERVER_KEY", "")
    raw = f"{order_id}{status_code}{gross_amount}{server_key}"
    expected = hashlib.sha512(raw.encode()).hexdigest()
    return hmac.compare_digest(expected, signature_key)


class InitiateQRISView(APIView):
    """POST /api/v1/payments/initiate-qris/"""

    permission_classes = [IsAuthenticated]

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

        midtrans_order_id = order.order_number
        is_production = getattr(settings, "MIDTRANS_IS_PRODUCTION", False)
        base_url = (
            "https://api.midtrans.com" if is_production else "https://api.sandbox.midtrans.com"
        )

        payment_type = (
            "qris"
            if order.payment_method == Order.PaymentMethod.QRIS_MIDTRANS
            else "bank_transfer"
        )

        payload = {
            "payment_type": payment_type,
            "transaction_details": {
                "order_id": midtrans_order_id,
                "gross_amount": int(order.grand_total),
            },
        }
        if payment_type == "qris":
            payload["qris"] = {"acquirer": "gopay"}

        server_key = getattr(settings, "MIDTRANS_SERVER_KEY", "")
        try:
            resp = http_requests.post(
                f"{base_url}/v2/charge",
                json=payload,
                auth=(server_key, ""),
                timeout=10,
            )
            resp.raise_for_status()
            resp_data = resp.json()
        except Exception as exc:
            return StandardResponse(
                success=False,
                code="PAYMENT_GATEWAY_ERROR",
                message=str(exc),
                status=502,
                request=request,
            )

        qr_string = resp_data.get("qr_string")
        qr_image_url = resp_data.get("qr_image_url")
        transaction_id = resp_data.get("transaction_id")
        expires_at = timezone.now() + timedelta(minutes=15)

        pt = PaymentTransaction.objects.create(
            order=order,
            midtrans_order_id=midtrans_order_id,
            transaction_id=transaction_id,
            payment_type=payment_type,
            gross_amount=order.grand_total,
            qr_string=qr_string,
            qr_image_url=qr_image_url,
            expires_at=expires_at,
            transaction_status="pending",
            raw_request_payload=payload,
            raw_response_payload=resp_data,
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

    permission_classes = [AllowAny]

    def post(self, request):
        payload = request.data

        order_id = payload.get("order_id", "")
        status_code = payload.get("status_code", "")
        gross_amount = payload.get("gross_amount", "")
        signature_key = payload.get("signature_key", "")
        transaction_status = payload.get("transaction_status", "")
        transaction_time = payload.get("transaction_time", "")

        sig_valid = _verify_midtrans_signature(order_id, status_code, gross_amount, signature_key)

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

                if (
                    order.payment_status == Order.PaymentStatus.SETTLED
                    and transaction_status not in ("refund",)
                ):
                    MidtransWebhookLog.objects.create(
                        midtrans_order_id=order_id,
                        transaction_status=transaction_status,
                        signature_valid=True,
                        payload=payload,
                        processing_result=MidtransWebhookLog.ProcessingResult.IGNORED_OUT_OF_ORDER,
                    )
                    return StandardResponse(message="Out-of-order event ignored.", request=request)

                status_map = {
                    "settlement": Order.PaymentStatus.SETTLED,
                    "expire": Order.PaymentStatus.EXPIRED,
                    "deny": Order.PaymentStatus.DENIED,
                    "cancel": Order.PaymentStatus.FAILED,
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
                    order_data = OrderSerializer(order).data
                    _outlet_id = str(order.outlet_id)
                    _order_id = str(order.id)
                    transaction.on_commit(
                        lambda: _broadcast_settled(_outlet_id, _order_id, order_data)
                    )

        except Order.DoesNotExist:
            pass

        return StandardResponse(message="Webhook processed.", request=request)


def _broadcast_settled(outlet_id, order_id_str, order_data):
    from apps.realtime.broadcast import broadcast_to_kitchen, broadcast_to_order
    broadcast_to_kitchen(outlet_id, "order.created", order_data)
    broadcast_to_order(order_id_str, "payment.status_changed", {"payment_status": "SETTLED"})


class ManualSettleView(APIView):
    """POST /api/v1/payments/manual-settle/ — cashier confirms CASH/EDC."""

    permission_classes = [IsAuthenticated]

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
            order_data = OrderSerializer(order_locked).data
            transaction.on_commit(
                lambda: _broadcast_settled(_outlet_id, _order_id, order_data)
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

    def get(self, request, order_id):
        tenant = getattr(request, "tenant", None)
        actor_type = (tenant or {}).get("actor_type")

        if actor_type == "CUSTOMER":
            qs = Order.objects.filter(pk=order_id, customer=request.user)
        elif actor_type == "EMPLOYEE":
            qs = Order.objects.filter(
                pk=order_id,
                brand_id=tenant["brand_id"],
                outlet_id__in=tenant["outlet_ids"],
            )
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
