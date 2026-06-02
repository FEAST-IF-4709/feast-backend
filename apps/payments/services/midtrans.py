import hashlib
import hmac
from datetime import timedelta

import requests as http_requests
from django.conf import settings
from django.utils import timezone


class MidtransError(Exception):
    pass


class MidtransClient:
    def __init__(self):
        self.server_key = getattr(settings, "MIDTRANS_SERVER_KEY", "")
        self.is_production = getattr(settings, "MIDTRANS_IS_PRODUCTION", False)
        self._base_url = (
            "https://api.midtrans.com"
            if self.is_production
            else "https://api.sandbox.midtrans.com"
        )

    def charge_qris(self, order, customer_details=None, midtrans_order_id=None):
        effective_order_id = midtrans_order_id or order.order_number
        payload = {
            "payment_type": "qris",
            "transaction_details": {
                "order_id": effective_order_id,
                "gross_amount": int(order.grand_total),
            },
            "qris": {"acquirer": "gopay"},
        }
        if customer_details:
            payload["customer_details"] = customer_details

        try:
            resp = http_requests.post(
                f"{self._base_url}/v2/charge",
                json=payload,
                auth=(self.server_key, ""),
                timeout=10,
            )
            resp.raise_for_status()
            resp_data = resp.json()
        except Exception as exc:
            raise MidtransError(str(exc)) from exc

        return {
            "midtrans_order_id": effective_order_id,
            "qr_string": resp_data.get("qr_string"),
            "qr_image_url": resp_data.get("qr_image_url"),
            "transaction_id": resp_data.get("transaction_id"),
            "expires_at": timezone.now() + timedelta(minutes=15),
            "raw_request_payload": payload,
            "raw_response_payload": resp_data,
        }

    def verify_signature(self, order_id, status_code, gross_amount, signature_key):
        raw = f"{order_id}{status_code}{gross_amount}{self.server_key}"
        expected = hashlib.sha512(raw.encode()).hexdigest()
        return hmac.compare_digest(expected, signature_key)

    def parse_webhook_status(self, payload):
        from apps.orders.models import Order

        ts = payload.get("transaction_status", "")
        status_map = {
            "settlement": Order.PaymentStatus.SETTLED,
            "expire": Order.PaymentStatus.EXPIRED,
            "refund": Order.PaymentStatus.REFUNDED,
            "deny": None,
            "cancel": None,
            "pending": None,
        }
        return {
            "transaction_status": ts,
            "order_payment_status": status_map.get(ts),
        }
