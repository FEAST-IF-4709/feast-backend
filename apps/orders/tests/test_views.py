"""Tests for Order creation and read endpoints (Phase 6B)."""
import uuid
from decimal import Decimal

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.orders.models import Order, OrderItem, OrderStatusHistory
from apps.orders.views import (
    CustomerOrderListView,
    OrderCashierPOSCreateView,
    OrderDetailView,
    OrderQRTableCreateView,
)

factory = APIRequestFactory()


# ---------------------------------------------------------------------------
# Helper: build a fake request with tenant context
# ---------------------------------------------------------------------------

def _make_request(method, path, data=None, *, user, actor_type, brand_id,
                  outlet_ids, permissions=frozenset(), outlet_id=None):
    make_fn = getattr(factory, method)
    kwargs = {"format": "json"} if data is not None else {}
    req = make_fn(path, data, **kwargs) if data is not None else make_fn(path)
    req.user = user
    req.tenant = {
        "actor_type": actor_type,
        "brand_id": str(brand_id),
        "outlet_id": str(outlet_id or (outlet_ids[0] if outlet_ids else "")),
        "outlet_ids": [str(o) for o in outlet_ids],
        "permissions": permissions,
    }
    force_authenticate(req, user=user)
    return req


# ---------------------------------------------------------------------------
# POST /api/v1/orders/qr-table/
# ---------------------------------------------------------------------------

class TestQRTableOrderCreate:
    def test_employee_auth_rejected(self, db, brand_a, outlet_a, cashier_employee, cashier_perms):
        req = _make_request(
            "post", "/orders/qr-table/", {"table_id": str(uuid.uuid4()), "items": []},
            user=cashier_employee, actor_type="EMPLOYEE",
            brand_id=brand_a.pk, outlet_ids=[outlet_a.pk], permissions=cashier_perms,
        )
        resp = OrderQRTableCreateView.as_view()(req)
        assert resp.status_code == 403

    def test_creates_order_returns_201(self, db, customer, table_a, outlet_product_a, brand_a):
        req = _make_request(
            "post", "/orders/qr-table/",
            {
                "table_id": str(table_a.pk),
                "items": [{"outlet_product_id": str(outlet_product_a.pk), "quantity": 2}],
            },
            user=customer, actor_type="CUSTOMER",
            brand_id=brand_a.pk, outlet_ids=[],
        )
        resp = OrderQRTableCreateView.as_view()(req)
        assert resp.status_code == 201
        assert "order_number" in resp.data["data"]
        assert resp.data["data"]["order_number"].startswith("FT-")

    def test_product_snapshot_populated(self, db, customer, table_a, outlet_product_a, brand_a):
        req = _make_request(
            "post", "/orders/qr-table/",
            {
                "table_id": str(table_a.pk),
                "items": [{"outlet_product_id": str(outlet_product_a.pk), "quantity": 1}],
            },
            user=customer, actor_type="CUSTOMER",
            brand_id=brand_a.pk, outlet_ids=[],
        )
        OrderQRTableCreateView.as_view()(req)
        item = OrderItem.objects.filter(
            order__customer=customer,
            outlet_product=outlet_product_a,
        ).first()
        assert item is not None
        assert item.product_snapshot.get("name") == outlet_product_a.brand_product.name

    def test_order_status_history_created(self, db, customer, table_a, outlet_product_a, brand_a):
        req = _make_request(
            "post", "/orders/qr-table/",
            {
                "table_id": str(table_a.pk),
                "items": [{"outlet_product_id": str(outlet_product_a.pk), "quantity": 1}],
            },
            user=customer, actor_type="CUSTOMER",
            brand_id=brand_a.pk, outlet_ids=[],
        )
        OrderQRTableCreateView.as_view()(req)
        order = Order.objects.get(customer=customer, order_source="QR_TABLE")
        history = OrderStatusHistory.objects.filter(order=order)
        assert history.count() == 1
        row = history.first()
        assert row.from_status is None
        assert row.to_status == Order.FulfillmentStatus.RECEIVED

    def test_out_of_stock_returns_400(self, db, customer, table_a,
                                       outlet_product_out_of_stock, brand_a):
        req = _make_request(
            "post", "/orders/qr-table/",
            {
                "table_id": str(table_a.pk),
                "items": [{"outlet_product_id": str(outlet_product_out_of_stock.pk), "quantity": 1}],
            },
            user=customer, actor_type="CUSTOMER",
            brand_id=brand_a.pk, outlet_ids=[],
        )
        resp = OrderQRTableCreateView.as_view()(req)
        assert resp.status_code == 400

    def test_invalid_table_id_returns_400(self, db, customer, outlet_product_a, brand_a):
        req = _make_request(
            "post", "/orders/qr-table/",
            {
                "table_id": str(uuid.uuid4()),  # non-existent
                "items": [{"outlet_product_id": str(outlet_product_a.pk), "quantity": 1}],
            },
            user=customer, actor_type="CUSTOMER",
            brand_id=brand_a.pk, outlet_ids=[],
        )
        resp = OrderQRTableCreateView.as_view()(req)
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/v1/orders/cashier-pos/
# ---------------------------------------------------------------------------

class TestCashierPOSOrderCreate:
    def _valid_payload(self, outlet_product_a, **overrides):
        data = {
            "items": [{"outlet_product_id": str(outlet_product_a.pk), "quantity": 1}],
            "payment_method": "CASH",
            "walk_in_name": "Pak Budi",
        }
        data.update(overrides)
        return data

    def test_customer_auth_rejected(self, db, customer, brand_a, outlet_a, outlet_product_a):
        req = _make_request(
            "post", "/orders/cashier-pos/",
            self._valid_payload(outlet_product_a),
            user=customer, actor_type="CUSTOMER",
            brand_id=brand_a.pk, outlet_ids=[],
        )
        resp = OrderCashierPOSCreateView.as_view()(req)
        assert resp.status_code == 403

    def test_missing_permission_rejected(self, db, cashier_employee, brand_a, outlet_a,
                                          outlet_product_a):
        req = _make_request(
            "post", "/orders/cashier-pos/",
            self._valid_payload(outlet_product_a),
            user=cashier_employee, actor_type="EMPLOYEE",
            brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=frozenset(),  # no permissions
        )
        resp = OrderCashierPOSCreateView.as_view()(req)
        assert resp.status_code == 403

    def test_walk_in_no_customer(self, db, cashier_employee, brand_a, outlet_a,
                                  outlet_product_a, cashier_perms):
        req = _make_request(
            "post", "/orders/cashier-pos/",
            self._valid_payload(outlet_product_a),
            user=cashier_employee, actor_type="EMPLOYEE",
            brand_id=brand_a.pk, outlet_ids=[outlet_a.pk], permissions=cashier_perms,
        )
        resp = OrderCashierPOSCreateView.as_view()(req)
        assert resp.status_code == 201
        order = Order.objects.get(pk=resp.data["data"]["id"])
        assert order.customer is None
        assert order.walk_in_name == "Pak Budi"

    def test_with_customer_id(self, db, cashier_employee, customer, brand_a, outlet_a,
                               outlet_product_a, cashier_perms):
        req = _make_request(
            "post", "/orders/cashier-pos/",
            self._valid_payload(outlet_product_a, customer_id=str(customer.pk)),
            user=cashier_employee, actor_type="EMPLOYEE",
            brand_id=brand_a.pk, outlet_ids=[outlet_a.pk], permissions=cashier_perms,
        )
        resp = OrderCashierPOSCreateView.as_view()(req)
        assert resp.status_code == 201
        order = Order.objects.get(pk=resp.data["data"]["id"])
        assert str(order.customer_id) == str(customer.pk)

    def test_cross_brand_outlet_rejected(self, db, cashier_employee, brand_a, outlet_a,
                                          outlet_b, outlet_product_a, cashier_perms):
        """Cashier from brand_a cannot create orders for outlet_b (brand_b)."""
        req = _make_request(
            "post", "/orders/cashier-pos/",
            self._valid_payload(outlet_product_a, outlet_id=str(outlet_b.pk)),
            user=cashier_employee, actor_type="EMPLOYEE",
            brand_id=brand_a.pk, outlet_ids=[outlet_a.pk], permissions=cashier_perms,
        )
        resp = OrderCashierPOSCreateView.as_view()(req)
        assert resp.status_code == 400

    def test_out_of_stock_returns_400(self, db, cashier_employee, brand_a, outlet_a,
                                       outlet_product_out_of_stock, cashier_perms):
        req = _make_request(
            "post", "/orders/cashier-pos/",
            {
                "items": [{"outlet_product_id": str(outlet_product_out_of_stock.pk), "quantity": 1}],
                "payment_method": "CASH",
            },
            user=cashier_employee, actor_type="EMPLOYEE",
            brand_id=brand_a.pk, outlet_ids=[outlet_a.pk], permissions=cashier_perms,
        )
        resp = OrderCashierPOSCreateView.as_view()(req)
        assert resp.status_code == 400

    def test_status_history_created(self, db, cashier_employee, brand_a, outlet_a,
                                     outlet_product_a, cashier_perms):
        req = _make_request(
            "post", "/orders/cashier-pos/",
            self._valid_payload(outlet_product_a),
            user=cashier_employee, actor_type="EMPLOYEE",
            brand_id=brand_a.pk, outlet_ids=[outlet_a.pk], permissions=cashier_perms,
        )
        resp = OrderCashierPOSCreateView.as_view()(req)
        assert resp.status_code == 201
        order = Order.objects.get(pk=resp.data["data"]["id"])
        history = OrderStatusHistory.objects.filter(order=order)
        assert history.count() == 1
        assert history.first().from_status is None


# ---------------------------------------------------------------------------
# GET /api/v1/orders/{pk}/
# ---------------------------------------------------------------------------

class TestOrderDetailView:
    def test_customer_sees_own_order(self, db, customer, qr_table_order, brand_a):
        req = _make_request(
            "get", f"/orders/{qr_table_order.pk}/",
            user=customer, actor_type="CUSTOMER",
            brand_id=brand_a.pk, outlet_ids=[],
        )
        resp = OrderDetailView.as_view()(req, pk=qr_table_order.pk)
        assert resp.status_code == 200
        assert resp.data["data"]["id"] == str(qr_table_order.pk)
        assert "status_history" in resp.data["data"]

    def test_customer_cannot_see_other_order(self, db, customer_b, qr_table_order, brand_a):
        req = _make_request(
            "get", f"/orders/{qr_table_order.pk}/",
            user=customer_b, actor_type="CUSTOMER",
            brand_id=brand_a.pk, outlet_ids=[],
        )
        resp = OrderDetailView.as_view()(req, pk=qr_table_order.pk)
        assert resp.status_code == 404

    def test_employee_sees_brand_order(self, db, cashier_employee, qr_table_order,
                                        brand_a, outlet_a, cashier_perms):
        req = _make_request(
            "get", f"/orders/{qr_table_order.pk}/",
            user=cashier_employee, actor_type="EMPLOYEE",
            brand_id=brand_a.pk, outlet_ids=[outlet_a.pk], permissions=cashier_perms,
        )
        resp = OrderDetailView.as_view()(req, pk=qr_table_order.pk)
        assert resp.status_code == 200

    def test_employee_cannot_see_cross_brand_order(self, db, cashier_employee, brand_a,
                                                    outlet_a, outlet_b, customer,
                                                    cashier_perms, brand_b):
        """Order belongs to brand_b — cashier from brand_a must get 404."""
        from apps.orders.models import Order
        from apps.staff.models import Employee
        brand_b_cashier_role = __import__(
            "apps.rbac.models", fromlist=["Role"]
        ).Role.objects.create(brand=brand_b, name="CASHIER_B", is_system=False)
        brand_b_cashier = Employee(
            brand=brand_b, outlet=outlet_b, role=brand_b_cashier_role,
            email="cashierb@test.com", full_name="Cashier B",
        )
        brand_b_cashier.set_password("x")
        brand_b_cashier.save()

        order_b = Order.objects.create(
            brand=brand_b, outlet=outlet_b,
            cashier_employee=brand_b_cashier,
            order_source=Order.OrderSource.CASHIER_POS,
            payment_method=Order.PaymentMethod.CASH,
            payment_status=Order.PaymentStatus.PENDING,
            grand_total=Decimal("10000.00"),
        )
        req = _make_request(
            "get", f"/orders/{order_b.pk}/",
            user=cashier_employee, actor_type="EMPLOYEE",
            brand_id=brand_a.pk, outlet_ids=[outlet_a.pk], permissions=cashier_perms,
        )
        resp = OrderDetailView.as_view()(req, pk=order_b.pk)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/me/orders/
# ---------------------------------------------------------------------------

class TestCustomerOrderListView:
    def test_returns_only_own_orders(self, db, customer, customer_b, brand_a, outlet_a,
                                      cashier_employee, cashier_perms):
        from apps.orders.models import Order
        # Create one order for customer and one for customer_b
        Order.objects.create(
            brand=brand_a, outlet=outlet_a, customer=customer,
            cashier_employee=cashier_employee,
            order_source=Order.OrderSource.CASHIER_POS,
            payment_method=Order.PaymentMethod.CASH,
            payment_status=Order.PaymentStatus.PENDING,
            grand_total=Decimal("10000.00"),
        )
        Order.objects.create(
            brand=brand_a, outlet=outlet_a, customer=customer_b,
            cashier_employee=cashier_employee,
            order_source=Order.OrderSource.CASHIER_POS,
            payment_method=Order.PaymentMethod.CASH,
            payment_status=Order.PaymentStatus.PENDING,
            grand_total=Decimal("5000.00"),
        )

        req = _make_request(
            "get", "/me/orders/",
            user=customer, actor_type="CUSTOMER",
            brand_id=uuid.uuid4(), outlet_ids=[],
        )
        resp = CustomerOrderListView.as_view()(req)
        assert resp.status_code == 200
        ids = [o["customer_id"] for o in resp.data["data"]]
        assert all(str(i) == str(customer.pk) for i in ids)
        assert len(ids) == 1

    def test_employee_auth_rejected(self, db, cashier_employee, brand_a, outlet_a, cashier_perms):
        req = _make_request(
            "get", "/me/orders/",
            user=cashier_employee, actor_type="EMPLOYEE",
            brand_id=brand_a.pk, outlet_ids=[outlet_a.pk], permissions=cashier_perms,
        )
        resp = CustomerOrderListView.as_view()(req)
        assert resp.status_code == 403
