import hashlib
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.orders.models import Order
from apps.payments.models import MidtransWebhookLog, PaymentTransaction
from apps.payments.views import InitiateQRISView, ManualSettleView, MidtransWebhookView

from .conftest import make_customer_request, make_employee_request, make_webhook_request


def _sig(order_id, status_code, gross_amount, server_key="test-key"):
    raw = f"{order_id}{status_code}{gross_amount}{server_key}"
    return hashlib.sha512(raw.encode()).hexdigest()


class TestInitiateQRIS:
    def test_success_creates_payment_transaction(self, db, pending_qris_order, cashier_emp, settings):
        settings.MIDTRANS_SERVER_KEY = "test-key"
        fake_result = {
            "transaction_id": "txn-abc123",
            "qr_string": "00020101test",
            "qr_image_url": "https://example.com/qr.png",
            "expires_at": timezone.now() + timedelta(minutes=15),
            "raw_request_payload": {"payment_type": "qris"},
            "raw_response_payload": {},
        }
        with patch("apps.payments.views.MidtransClient") as MockClient:
            MockClient.return_value.charge_qris.return_value = fake_result
            req = make_customer_request(
                "post", "/initiate-qris/",
                {"order_id": str(pending_qris_order.id)},
                user=cashier_emp,
            )
            resp = InitiateQRISView.as_view()(req)

        assert resp.status_code == 201
        assert PaymentTransaction.objects.filter(order=pending_qris_order).count() == 1
        assert resp.data["data"]["qr_string"] == "00020101test"

    def test_idempotent_returns_existing_active_transaction(self, db, pending_qris_order, cashier_emp):
        PaymentTransaction.objects.create(
            order=pending_qris_order,
            midtrans_order_id=pending_qris_order.order_number,
            transaction_id="existing-txn",
            payment_type="qris",
            gross_amount=pending_qris_order.grand_total,
            qr_string="existing-qr",
            qr_image_url="https://example.com/existing.png",
            expires_at=timezone.now() + timedelta(hours=1),
            transaction_status="pending",
            raw_request_payload={},
            raw_response_payload={},
        )
        req = make_customer_request(
            "post", "/initiate-qris/",
            {"order_id": str(pending_qris_order.id)},
            user=cashier_emp,
        )
        resp = InitiateQRISView.as_view()(req)

        assert resp.status_code == 200
        assert PaymentTransaction.objects.filter(order=pending_qris_order).count() == 1


class TestMidtransWebhook:
    def test_invalid_signature_returns_403(self, db):
        payload = {
            "order_id": "ORD-FAKE",
            "status_code": "200",
            "gross_amount": "50000.00",
            "signature_key": "bad-signature",
            "transaction_status": "settlement",
            "transaction_time": "2025-01-01 10:00:00",
        }
        resp = MidtransWebhookView.as_view()(make_webhook_request(payload))

        assert resp.status_code == 403
        assert MidtransWebhookLog.objects.filter(
            midtrans_order_id="ORD-FAKE",
            processing_result=MidtransWebhookLog.ProcessingResult.REJECTED_INVALID_SIG,
        ).exists()

    def test_settlement_sets_order_settled(self, db, pending_qris_order, settings):
        settings.MIDTRANS_SERVER_KEY = "test-key"
        order_number = pending_qris_order.order_number
        gross_amount = "75000.00"
        status_code = "200"
        payload = {
            "order_id": order_number,
            "status_code": status_code,
            "gross_amount": gross_amount,
            "signature_key": _sig(order_number, status_code, gross_amount),
            "transaction_status": "settlement",
            "transaction_time": "2025-01-01 10:00:00",
        }
        resp = MidtransWebhookView.as_view()(make_webhook_request(payload))

        assert resp.status_code == 200
        pending_qris_order.refresh_from_db()
        assert pending_qris_order.payment_status == Order.PaymentStatus.SETTLED
        assert MidtransWebhookLog.objects.filter(
            midtrans_order_id=order_number,
            processing_result=MidtransWebhookLog.ProcessingResult.APPLIED,
        ).exists()

    def test_duplicate_event_ignored(self, db, pending_qris_order, settings):
        settings.MIDTRANS_SERVER_KEY = "test-key"
        order_number = pending_qris_order.order_number
        transaction_time = "2025-01-01 10:00:00"
        MidtransWebhookLog.objects.create(
            midtrans_order_id=order_number,
            transaction_status="settlement",
            signature_valid=True,
            payload={"transaction_time": transaction_time},
            processing_result=MidtransWebhookLog.ProcessingResult.APPLIED,
        )
        gross_amount = "75000.00"
        status_code = "200"
        payload = {
            "order_id": order_number,
            "status_code": status_code,
            "gross_amount": gross_amount,
            "signature_key": _sig(order_number, status_code, gross_amount),
            "transaction_status": "settlement",
            "transaction_time": transaction_time,
        }
        resp = MidtransWebhookView.as_view()(make_webhook_request(payload))

        assert resp.status_code == 200
        assert MidtransWebhookLog.objects.filter(
            midtrans_order_id=order_number,
            processing_result=MidtransWebhookLog.ProcessingResult.IGNORED_DUPLICATE,
        ).exists()

    def test_settlement_after_expire_ignored(self, db, pending_qris_order, settings):
        settings.MIDTRANS_SERVER_KEY = "test-key"
        pending_qris_order.payment_status = Order.PaymentStatus.EXPIRED
        pending_qris_order.save(update_fields=["payment_status"])

        order_number = pending_qris_order.order_number
        gross_amount = "75000.00"
        status_code = "200"
        payload = {
            "order_id": order_number,
            "status_code": status_code,
            "gross_amount": gross_amount,
            "signature_key": _sig(order_number, status_code, gross_amount),
            "transaction_status": "settlement",
            "transaction_time": "2025-01-01 10:00:01",
        }
        resp = MidtransWebhookView.as_view()(make_webhook_request(payload))

        assert resp.status_code == 200
        pending_qris_order.refresh_from_db()
        assert pending_qris_order.payment_status == Order.PaymentStatus.EXPIRED
        assert MidtransWebhookLog.objects.filter(
            midtrans_order_id=order_number,
            processing_result=MidtransWebhookLog.ProcessingResult.IGNORED_OUT_OF_ORDER,
        ).exists()


class TestManualSettle:
    def test_cash_amount_less_than_grand_total_returns_400(self, db, pending_cash_order, cashier_emp):
        req = make_employee_request(
            "post", "/manual-settle/",
            {
                "order_id": str(pending_cash_order.id),
                "payment_method": "CASH",
                "amount_received": "40000.00",
                "change_given": "0.00",
            },
            user=cashier_emp,
            brand_id=pending_cash_order.brand_id,
            outlet_ids=[pending_cash_order.outlet_id],
            permissions=frozenset({"cashier.payment.settle_manual"}),
        )
        resp = ManualSettleView.as_view()(req)

        assert resp.status_code == 400

    def test_edc_without_reference_returns_400(self, db, pending_edc_order, cashier_emp):
        req = make_employee_request(
            "post", "/manual-settle/",
            {
                "order_id": str(pending_edc_order.id),
                "payment_method": "EDC",
                "amount_received": "50000.00",
                "change_given": "0.00",
            },
            user=cashier_emp,
            brand_id=pending_edc_order.brand_id,
            outlet_ids=[pending_edc_order.outlet_id],
            permissions=frozenset({"cashier.payment.settle_manual"}),
        )
        resp = ManualSettleView.as_view()(req)

        assert resp.status_code == 400
