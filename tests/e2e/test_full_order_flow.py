"""
E2E: Full order lifecycle — QR table scan → payment → kitchen completion.

Each test class represents one step of the flow and can be run independently.
External services (Midtrans) are mocked; everything else hits the real Django stack.
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from apps.orders.models import Order
from apps.rbac.models import Role


# ---------------------------------------------------------------------------
# Step 1: Brand → system roles
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestBrandSetup:
    def test_system_roles_exist_for_brand(self, brand, kitchen_role, cashier_role):
        """Fixture creates roles explicitly; verifies they are scoped to the brand."""
        roles = Role.objects.filter(brand=brand, is_system=True)
        assert roles.count() >= 2
        names = set(roles.values_list("name", flat=True))
        assert "KITCHEN" in names
        assert "CASHIER" in names


# ---------------------------------------------------------------------------
# Step 2: Customer register + login
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCustomerAuth:
    def test_customer_register(self, anon_client):
        resp = anon_client.post(
            "/api/v1/auth/customer/register/",
            {"phone": "+6289900000001", "full_name": "New Customer", "password": "Str0ngPass!"},
            format="json",
        )
        assert resp.status_code == 201
        assert "access" in resp.data["data"]
        assert "refresh" in resp.data["data"]

    def test_customer_login(self, anon_client, customer):
        resp = anon_client.post(
            "/api/v1/auth/customer/login/",
            {"phone": customer.phone, "password": "testpass123"},
            format="json",
        )
        assert resp.status_code == 200
        assert "access" in resp.data["data"]

    def test_customer_login_wrong_password(self, anon_client, customer):
        resp = anon_client.post(
            "/api/v1/auth/customer/login/",
            {"phone": customer.phone, "password": "wrongpass"},
            format="json",
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Step 3: QR resolve + outlet menu
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPublicQRFlow:
    def test_resolve_valid_qr_token(self, anon_client, table):
        resp = anon_client.get(f"/api/v1/public/tables/resolve/?token={table.qr_token}")
        assert resp.status_code == 200
        assert str(resp.data["data"]["outlet"]["id"]) == str(table.outlet_id)

    def test_resolve_invalid_qr_token(self, anon_client):
        resp = anon_client.get("/api/v1/public/tables/resolve/?token=invalid-token-xyz")
        assert resp.status_code == 404

    def test_outlet_menu(self, anon_client, outlet, outlet_product):
        resp = anon_client.get(f"/api/v1/public/outlets/{outlet.id}/menu/")
        assert resp.status_code == 200
        menu = resp.data["data"]["menu"]
        assert len(menu) >= 1
        assert menu[0]["items"][0]["name"] == "Nasi Goreng Spesial"


# ---------------------------------------------------------------------------
# Step 4: Customer creates QR table order
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCustomerOrderCreation:
    def test_create_qr_table_order(self, customer_client, table, outlet_product):
        resp = customer_client.post(
            "/api/v1/orders/qr-table/",
            {
                "table_id": str(table.id),
                "items": [{"outlet_product_id": str(outlet_product.id), "quantity": 2}],
            },
            format="json",
        )
        assert resp.status_code == 201
        data = resp.data["data"]
        assert "order_id" in data
        assert "order_number" in data
        assert Decimal(data["grand_total"]) == Decimal("70000.00")

    def test_create_order_invalid_product(self, customer_client, table):
        import uuid
        resp = customer_client.post(
            "/api/v1/orders/qr-table/",
            {
                "table_id": str(table.id),
                "items": [{"outlet_product_id": str(uuid.uuid4()), "quantity": 1}],
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_unauthenticated_cannot_create_order(self, anon_client, table, outlet_product):
        resp = anon_client.post(
            "/api/v1/orders/qr-table/",
            {"table_id": str(table.id), "items": []},
            format="json",
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Step 5: QRIS payment initiation + webhook settlement
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPaymentFlow:
    def _create_qris_order(self, brand, outlet, customer, table):
        """Create a PENDING order with QRIS payment method for payment tests."""
        return Order.objects.create(
            brand=brand,
            outlet=outlet,
            customer=customer,
            table=table,
            order_source=Order.OrderSource.QR_TABLE,
            payment_method=Order.PaymentMethod.QRIS_MIDTRANS,
            payment_status=Order.PaymentStatus.PENDING,
            fulfillment_status=Order.FulfillmentStatus.RECEIVED,
            subtotal=Decimal("35000.00"),
            grand_total=Decimal("35000.00"),
        )

    def test_initiate_qris_payment(self, customer_client, brand, outlet, customer, table):
        order = self._create_qris_order(brand, outlet, customer, table)

        mock_result = {
            "transaction_id": "txn-test-001",
            "qr_string": "00020101...",
            "qr_image_url": "https://api.midtrans.com/qr.png",
            "expires_at": "2099-12-31T23:59:59Z",
            "raw_request_payload": {},
            "raw_response_payload": {},
        }

        with patch("apps.payments.views.MidtransClient") as MockClient:
            MockClient.return_value.charge_qris.return_value = mock_result
            resp = customer_client.post(
                "/api/v1/payments/initiate-qris/",
                {"order_id": str(order.id)},
                format="json",
            )

        assert resp.status_code == 201
        data = resp.data["data"]
        assert data["transaction_id"] == "txn-test-001"
        assert "qr_string" in data

    def test_webhook_settles_order(self, anon_client, brand, outlet, customer, table):
        order = self._create_qris_order(brand, outlet, customer, table)
        order.order_number = "FEAST-TEST-001"
        order.save(update_fields=["order_number"])

        payload = {
            "order_id": order.order_number,
            "status_code": "200",
            "gross_amount": "35000.00",
            "signature_key": "valid-sig",
            "transaction_status": "settlement",
            "transaction_time": "2099-01-01 10:00:00",
        }

        with patch("apps.payments.views.MidtransClient") as MockClient:
            MockClient.return_value.verify_signature.return_value = True
            resp = anon_client.post("/api/v1/payments/webhook/midtrans/", payload, format="json")

        assert resp.status_code == 200
        order.refresh_from_db()
        assert order.payment_status == Order.PaymentStatus.SETTLED

    def test_webhook_invalid_signature_rejected(self, anon_client, brand, outlet, customer, table):
        order = self._create_qris_order(brand, outlet, customer, table)
        payload = {
            "order_id": order.order_number,
            "status_code": "200",
            "gross_amount": "35000.00",
            "signature_key": "bad-sig",
            "transaction_status": "settlement",
            "transaction_time": "2099-01-01 10:00:00",
        }
        with patch("apps.payments.views.MidtransClient") as MockClient:
            MockClient.return_value.verify_signature.return_value = False
            resp = anon_client.post("/api/v1/payments/webhook/midtrans/", payload, format="json")

        assert resp.status_code == 403
        order.refresh_from_db()
        assert order.payment_status == Order.PaymentStatus.PENDING

    def test_payment_status_poll(self, customer_client, brand, outlet, customer, table):
        order = self._create_qris_order(brand, outlet, customer, table)
        resp = customer_client.get(f"/api/v1/payments/{order.id}/status/")
        assert resp.status_code == 200
        assert resp.data["data"]["payment_status"] == Order.PaymentStatus.PENDING


# ---------------------------------------------------------------------------
# Step 6: Kitchen staff — full fulfillment lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestKitchenFulfillmentLifecycle:
    def test_kitchen_sees_settled_order(self, kitchen_client, settled_order):
        resp = kitchen_client.get("/api/v1/kitchen/orders/")
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.data["data"]]
        assert str(settled_order.id) in ids

    def test_kitchen_does_not_see_other_brand_orders(self, kitchen_client, db):
        """Kitchen staff only see orders for their own brand."""
        from apps.tenants.models import Brand, Outlet
        other_brand = Brand.objects.create(name="Other Brand", slug="other-brand", owner_email="other@test.com")
        other_outlet = Outlet.objects.create(
            brand=other_brand, name="Other Outlet", address="x",
            latitude=Decimal("-6.0"), longitude=Decimal("106.0"),
        )
        other_order = Order.objects.create(
            brand=other_brand, outlet=other_outlet,
            order_source=Order.OrderSource.QR_TABLE,
            payment_status=Order.PaymentStatus.SETTLED,
            fulfillment_status=Order.FulfillmentStatus.RECEIVED,
            subtotal=Decimal("10000.00"), grand_total=Decimal("10000.00"),
        )
        resp = kitchen_client.get("/api/v1/kitchen/orders/")
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.data["data"]]
        assert str(other_order.id) not in ids

    def test_kitchen_status_received_to_in_progress(self, kitchen_client, settled_order):
        with patch("apps.kitchen.views._broadcast_status_change"), \
             patch("apps.kitchen.views.transaction.on_commit", side_effect=lambda f: f()):
            resp = kitchen_client.patch(
                f"/api/v1/kitchen/orders/{settled_order.id}/status/",
                {"to_status": "IN_PROGRESS"},
                format="json",
            )
        assert resp.status_code == 200
        settled_order.refresh_from_db()
        assert settled_order.fulfillment_status == Order.FulfillmentStatus.IN_PROGRESS

    def test_kitchen_status_in_progress_to_ready(self, kitchen_client, settled_order):
        settled_order.fulfillment_status = Order.FulfillmentStatus.IN_PROGRESS
        settled_order.save(update_fields=["fulfillment_status"])

        with patch("apps.kitchen.views._broadcast_status_change"), \
             patch("apps.kitchen.views.transaction.on_commit", side_effect=lambda f: f()):
            resp = kitchen_client.patch(
                f"/api/v1/kitchen/orders/{settled_order.id}/status/",
                {"to_status": "READY"},
                format="json",
            )
        assert resp.status_code == 200
        settled_order.refresh_from_db()
        assert settled_order.fulfillment_status == Order.FulfillmentStatus.READY

    def test_kitchen_status_ready_to_served(self, kitchen_client, settled_order):
        settled_order.fulfillment_status = Order.FulfillmentStatus.READY
        settled_order.save(update_fields=["fulfillment_status"])

        with patch("apps.kitchen.views._broadcast_status_change"), \
             patch("apps.kitchen.views.transaction.on_commit", side_effect=lambda f: f()):
            resp = kitchen_client.patch(
                f"/api/v1/kitchen/orders/{settled_order.id}/status/",
                {"to_status": "SERVED"},
                format="json",
            )
        assert resp.status_code == 200
        settled_order.refresh_from_db()
        assert settled_order.fulfillment_status == Order.FulfillmentStatus.SERVED

    def test_kitchen_status_served_to_completed(self, kitchen_client, settled_order):
        settled_order.fulfillment_status = Order.FulfillmentStatus.SERVED
        settled_order.save(update_fields=["fulfillment_status"])

        with patch("apps.kitchen.views._broadcast_status_change"), \
             patch("apps.kitchen.views.transaction.on_commit", side_effect=lambda f: f()):
            resp = kitchen_client.patch(
                f"/api/v1/kitchen/orders/{settled_order.id}/status/",
                {"to_status": "COMPLETED"},
                format="json",
            )
        assert resp.status_code == 200
        settled_order.refresh_from_db()
        assert settled_order.fulfillment_status == Order.FulfillmentStatus.COMPLETED

    def test_kitchen_force_cancel(self, kitchen_client, settled_order):
        with patch("apps.kitchen.views._broadcast_cancel"), \
             patch("apps.kitchen.views.transaction.on_commit", side_effect=lambda f: f()):
            resp = kitchen_client.post(
                f"/api/v1/kitchen/orders/{settled_order.id}/cancel/",
                {"cancel_reason": "Customer request — E2E test"},
                format="json",
            )
        assert resp.status_code == 200
        settled_order.refresh_from_db()
        assert settled_order.fulfillment_status == Order.FulfillmentStatus.CANCELLED

    def test_kitchen_invalid_transition_rejected(self, kitchen_client, settled_order):
        # Cannot jump from RECEIVED directly to COMPLETED
        with patch("apps.kitchen.views.transaction.on_commit", side_effect=lambda f: f()):
            resp = kitchen_client.patch(
                f"/api/v1/kitchen/orders/{settled_order.id}/status/",
                {"to_status": "COMPLETED"},
                format="json",
            )
        assert resp.status_code == 409

    def test_kitchen_missing_permission_denied(self, customer_client, settled_order):
        """Customer JWT cannot access kitchen endpoints."""
        resp = customer_client.get("/api/v1/kitchen/orders/")
        assert resp.status_code == 403
