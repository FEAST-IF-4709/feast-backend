import hashlib
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from apps.payments.services.midtrans import MidtransClient, MidtransError


@pytest.fixture
def client(settings):
    settings.MIDTRANS_SERVER_KEY = "test-server-key"
    settings.MIDTRANS_IS_PRODUCTION = False
    return MidtransClient()


class TestVerifySignature:
    def test_valid_signature_returns_true(self, client):
        order_id, status_code, gross_amount = "ORD-001", "200", "50000.00"
        raw = f"{order_id}{status_code}{gross_amount}test-server-key"
        valid_sig = hashlib.sha512(raw.encode()).hexdigest()
        assert client.verify_signature(order_id, status_code, gross_amount, valid_sig) is True

    def test_tampered_signature_returns_false(self, client):
        assert client.verify_signature("ORD-001", "200", "50000.00", "bad-sig") is False

    def test_wrong_amount_returns_false(self, client):
        order_id, status_code, gross_amount = "ORD-001", "200", "50000.00"
        raw = f"{order_id}{status_code}99999.00test-server-key"
        wrong_sig = hashlib.sha512(raw.encode()).hexdigest()
        assert client.verify_signature(order_id, status_code, gross_amount, wrong_sig) is False


class TestChargeQris:
    def _make_order(self):
        order = MagicMock()
        order.order_number = "ORD-TEST-001"
        order.grand_total = Decimal("75000")
        return order

    def test_returns_expected_keys_on_success(self, client):
        mock_response = {
            "transaction_id": "mid-txn-abc",
            "qr_string": "00020101...",
            "qr_image_url": "https://example.com/qr.png",
            "transaction_status": "pending",
        }
        with patch("apps.payments.services.midtrans.http_requests.post") as mock_post:
            mock_post.return_value.json.return_value = mock_response
            mock_post.return_value.raise_for_status = lambda: None

            result = client.charge_qris(self._make_order())

        assert result["qr_string"] == "00020101..."
        assert result["qr_image_url"] == "https://example.com/qr.png"
        assert result["transaction_id"] == "mid-txn-abc"
        assert "expires_at" in result
        assert result["raw_request_payload"]["payment_type"] == "qris"
        assert result["raw_request_payload"]["transaction_details"]["gross_amount"] == 75000

    def test_raises_midtrans_error_on_http_failure(self, client):
        with patch("apps.payments.services.midtrans.http_requests.post") as mock_post:
            mock_post.side_effect = Exception("Connection refused")
            with pytest.raises(MidtransError):
                client.charge_qris(self._make_order())
