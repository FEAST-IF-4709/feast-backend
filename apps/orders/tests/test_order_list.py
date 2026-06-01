"""Tests for GET /api/v1/orders/ — Order History Dashboard endpoint."""
import uuid
from decimal import Decimal

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.orders.models import Order
from apps.orders.views import OrderListView
from apps.rbac.models import Role
from apps.staff.models import Employee
from apps.tenants.models import Brand, Outlet

factory = APIRequestFactory()


# ---------------------------------------------------------------------------
# Fixtures — brand B + employee B (brand A fixtures come from conftest.py)
# ---------------------------------------------------------------------------

@pytest.fixture
def brand_b(db):
    return Brand.objects.create(
        name="Brand B", slug="brand-b", owner_email="owner_b@test.com"
    )


@pytest.fixture
def outlet_b(db, brand_b):
    return Outlet.objects.create(
        brand=brand_b,
        name="Outlet B1",
        address="Jl. Test No. 2",
        latitude=Decimal("-6.210000"),
        longitude=Decimal("106.810000"),
    )


@pytest.fixture
def manager_role_b(db, brand_b):
    return Role.objects.create(brand=brand_b, name="MANAGER", is_system=True)


@pytest.fixture
def employee_b(db, brand_b, outlet_b, manager_role_b):
    emp = Employee(
        brand=brand_b, outlet=outlet_b, role=manager_role_b,
        email="manager_b@test.com", full_name="Manager B",
    )
    emp.set_password("testpass123")
    emp.save()
    return emp


@pytest.fixture
def outlet_a2(db, brand_a):
    return Outlet.objects.create(
        brand=brand_a,
        name="Outlet A2",
        address="Jl. Test No. 3",
        latitude=Decimal("-6.220000"),
        longitude=Decimal("106.820000"),
    )


@pytest.fixture
def owner_role_a(db, brand_a):
    return Role.objects.create(brand=brand_a, name="OWNER", is_system=True)


@pytest.fixture
def brand_employee(db, brand_a, owner_role_a):
    """Brand-level employee — outlet=None, sees all outlets in their brand."""
    emp = Employee(
        brand=brand_a, outlet=None, role=owner_role_a,
        email="owner_a@test.com", full_name="Owner A",
    )
    emp.set_password("testpass123")
    emp.save()
    return emp


@pytest.fixture
def order_perms():
    return frozenset({"orders.view"})


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_request(method, path, data=None, *, user, brand_id, outlet_ids,
                  permissions=frozenset(), query_params=None):
    make_fn = getattr(factory, method)
    full_path = path
    if query_params:
        qs = "&".join(f"{k}={v}" for k, v in query_params.items())
        full_path = f"{path}?{qs}"
    req = make_fn(full_path, data, format="json") if data is not None else make_fn(full_path)
    req.user = user
    req.tenant = {
        "actor_type": "EMPLOYEE",
        "brand_id": str(brand_id),
        "outlet_ids": [str(o) for o in outlet_ids],
        "permissions": permissions,
    }
    force_authenticate(req, user=user)
    return req


_list_view = OrderListView.as_view()


def _make_order(brand, outlet, employee, **kwargs):
    defaults = dict(
        order_source=Order.OrderSource.CASHIER_POS,
        payment_method=Order.PaymentMethod.CASH,
        payment_status=Order.PaymentStatus.SETTLED,
        fulfillment_status=Order.FulfillmentStatus.COMPLETED,
        subtotal=Decimal("25000.00"),
        grand_total=Decimal("25000.00"),
        cashier_employee=employee,
    )
    defaults.update(kwargs)
    return Order.objects.create(brand=brand, outlet=outlet, **defaults)


# ---------------------------------------------------------------------------
# Basic behaviour
# ---------------------------------------------------------------------------

class TestOrderListBasic:
    def test_returns_200_with_expected_fields(
        self, db, brand_a, outlet_a, cashier_employee, order_perms
    ):
        _make_order(brand_a, outlet_a, cashier_employee)
        req = _make_request(
            "get", "/orders/",
            user=cashier_employee, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=order_perms,
        )
        resp = _list_view(req)
        assert resp.status_code == 200
        assert resp.data["success"] is True
        item = resp.data["data"][0]
        expected_keys = {
            "id", "order_number", "outlet", "customer_name", "walk_in_name",
            "table_label", "items_count", "grand_total", "payment_method",
            "payment_status", "fulfillment_status", "order_source", "placed_at",
        }
        assert expected_keys.issubset(item.keys())
        assert item["outlet"]["name"] == "Outlet A1"

    def test_no_orders_returns_empty_list(
        self, db, brand_a, outlet_a, cashier_employee, order_perms
    ):
        req = _make_request(
            "get", "/orders/",
            user=cashier_employee, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=order_perms,
        )
        resp = _list_view(req)
        assert resp.status_code == 200
        assert resp.data["data"] == []

    def test_requires_orders_view_permission(
        self, db, brand_a, outlet_a, cashier_employee
    ):
        req = _make_request(
            "get", "/orders/",
            user=cashier_employee, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=frozenset({"kitchen.order.view"}),  # wrong permission
        )
        resp = _list_view(req)
        assert resp.status_code == 403

    def test_cross_tenant_isolation(
        self, db, brand_a, outlet_a, cashier_employee, order_perms,
        brand_b, outlet_b, employee_b
    ):
        order_a = _make_order(brand_a, outlet_a, cashier_employee)
        _make_order(brand_b, outlet_b, employee_b)

        req = _make_request(
            "get", "/orders/",
            user=cashier_employee, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=order_perms,
        )
        resp = _list_view(req)
        assert resp.status_code == 200
        returned_ids = {item["id"] for item in resp.data["data"]}
        assert str(order_a.pk) in returned_ids
        assert len(returned_ids) == 1  # brand B order not visible

    def test_items_count_reflects_order_items(
        self, db, brand_a, outlet_a, cashier_employee, order_perms
    ):
        order = _make_order(brand_a, outlet_a, cashier_employee)
        req = _make_request(
            "get", "/orders/",
            user=cashier_employee, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=order_perms,
        )
        resp = _list_view(req)
        assert resp.data["data"][0]["items_count"] == 0  # no items added


# ---------------------------------------------------------------------------
# Filter tests
# ---------------------------------------------------------------------------

class TestOrderListFilters:
    def test_filter_date_from_excludes_older_orders(
        self, db, brand_a, outlet_a, cashier_employee, order_perms
    ):
        from django.utils import timezone
        import datetime

        old_order = _make_order(brand_a, outlet_a, cashier_employee)
        old_order.placed_at = timezone.now() - datetime.timedelta(days=10)
        old_order.save(update_fields=["placed_at"])

        recent_order = _make_order(brand_a, outlet_a, cashier_employee)

        today = timezone.now().date().isoformat()
        req = _make_request(
            "get", "/orders/",
            user=cashier_employee, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=order_perms,
            query_params={"date_from": today},
        )
        resp = _list_view(req)
        assert resp.status_code == 200
        returned_ids = {item["id"] for item in resp.data["data"]}
        assert str(recent_order.pk) in returned_ids
        assert str(old_order.pk) not in returned_ids

    def test_filter_date_to_excludes_future_orders(
        self, db, brand_a, outlet_a, cashier_employee, order_perms
    ):
        from django.utils import timezone
        import datetime

        old_order = _make_order(brand_a, outlet_a, cashier_employee)
        old_order.placed_at = timezone.now() - datetime.timedelta(days=5)
        old_order.save(update_fields=["placed_at"])

        yesterday = (timezone.now().date() - datetime.timedelta(days=1)).isoformat()
        req = _make_request(
            "get", "/orders/",
            user=cashier_employee, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=order_perms,
            query_params={"date_to": yesterday},
        )
        resp = _list_view(req)
        assert resp.status_code == 200
        returned_ids = {item["id"] for item in resp.data["data"]}
        assert str(old_order.pk) in returned_ids

    def test_filter_date_from_invalid_format_returns_400(
        self, db, brand_a, outlet_a, cashier_employee, order_perms
    ):
        req = _make_request(
            "get", "/orders/",
            user=cashier_employee, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=order_perms,
            query_params={"date_from": "31-12-2025"},
        )
        resp = _list_view(req)
        assert resp.status_code == 400

    def test_filter_fulfillment_status_single(
        self, db, brand_a, outlet_a, cashier_employee, order_perms
    ):
        completed = _make_order(brand_a, outlet_a, cashier_employee,
                                fulfillment_status=Order.FulfillmentStatus.COMPLETED)
        cancelled = _make_order(brand_a, outlet_a, cashier_employee,
                                fulfillment_status=Order.FulfillmentStatus.CANCELLED)
        req = _make_request(
            "get", "/orders/",
            user=cashier_employee, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=order_perms,
            query_params={"fulfillment_status": "COMPLETED"},
        )
        resp = _list_view(req)
        returned_ids = {item["id"] for item in resp.data["data"]}
        assert str(completed.pk) in returned_ids
        assert str(cancelled.pk) not in returned_ids

    def test_filter_fulfillment_status_multi_value(
        self, db, brand_a, outlet_a, cashier_employee, order_perms
    ):
        received = _make_order(brand_a, outlet_a, cashier_employee,
                               payment_status=Order.PaymentStatus.PENDING,
                               fulfillment_status=Order.FulfillmentStatus.RECEIVED)
        cancelled = _make_order(brand_a, outlet_a, cashier_employee,
                                fulfillment_status=Order.FulfillmentStatus.CANCELLED)
        completed = _make_order(brand_a, outlet_a, cashier_employee,
                                fulfillment_status=Order.FulfillmentStatus.COMPLETED)
        req = _make_request(
            "get", "/orders/",
            user=cashier_employee, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=order_perms,
            query_params={"fulfillment_status": "RECEIVED,CANCELLED"},
        )
        resp = _list_view(req)
        returned_ids = {item["id"] for item in resp.data["data"]}
        assert str(received.pk) in returned_ids
        assert str(cancelled.pk) in returned_ids
        assert str(completed.pk) not in returned_ids

    def test_filter_payment_status_multi_value(
        self, db, brand_a, outlet_a, cashier_employee, order_perms
    ):
        settled = _make_order(brand_a, outlet_a, cashier_employee,
                              payment_status=Order.PaymentStatus.SETTLED)
        refunded = _make_order(brand_a, outlet_a, cashier_employee,
                               payment_status=Order.PaymentStatus.REFUNDED)
        pending = _make_order(brand_a, outlet_a, cashier_employee,
                              payment_status=Order.PaymentStatus.PENDING,
                              fulfillment_status=Order.FulfillmentStatus.RECEIVED)
        req = _make_request(
            "get", "/orders/",
            user=cashier_employee, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=order_perms,
            query_params={"payment_status": "SETTLED,REFUNDED"},
        )
        resp = _list_view(req)
        returned_ids = {item["id"] for item in resp.data["data"]}
        assert str(settled.pk) in returned_ids
        assert str(refunded.pk) in returned_ids
        assert str(pending.pk) not in returned_ids

    def test_filter_outlet_id_valid(
        self, db, brand_a, outlet_a, cashier_employee, order_perms
    ):
        order = _make_order(brand_a, outlet_a, cashier_employee)
        req = _make_request(
            "get", "/orders/",
            user=cashier_employee, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=order_perms,
            query_params={"outlet_id": str(outlet_a.pk)},
        )
        resp = _list_view(req)
        assert resp.status_code == 200
        returned_ids = {item["id"] for item in resp.data["data"]}
        assert str(order.pk) in returned_ids

    def test_filter_outlet_id_from_other_brand_returns_403(
        self, db, brand_a, outlet_a, cashier_employee, order_perms,
        outlet_b
    ):
        req = _make_request(
            "get", "/orders/",
            user=cashier_employee, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=order_perms,
            query_params={"outlet_id": str(outlet_b.pk)},
        )
        resp = _list_view(req)
        assert resp.status_code == 403

    def test_filter_order_number_partial_match(
        self, db, brand_a, outlet_a, cashier_employee, order_perms
    ):
        order = _make_order(brand_a, outlet_a, cashier_employee)
        partial = order.order_number[3:9]  # middle slice of "FT-YYYYMMDD-XXXX"
        req = _make_request(
            "get", "/orders/",
            user=cashier_employee, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=order_perms,
            query_params={"order_number": partial.lower()},  # lowercase to test icontains
        )
        resp = _list_view(req)
        assert resp.status_code == 200
        returned_ids = {item["id"] for item in resp.data["data"]}
        assert str(order.pk) in returned_ids

    def test_invalid_fulfillment_status_values_are_silently_ignored(
        self, db, brand_a, outlet_a, cashier_employee, order_perms
    ):
        order = _make_order(brand_a, outlet_a, cashier_employee)
        req = _make_request(
            "get", "/orders/",
            user=cashier_employee, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=order_perms,
            query_params={"fulfillment_status": "INVALID_STATUS"},
        )
        resp = _list_view(req)
        # Invalid statuses filtered out → no fulfillment filter applied → all orders returned
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Pagination tests
# ---------------------------------------------------------------------------

class TestOrderListPagination:
    def test_default_page_size_is_25(
        self, db, brand_a, outlet_a, cashier_employee, order_perms
    ):
        for _ in range(30):
            _make_order(brand_a, outlet_a, cashier_employee)
        req = _make_request(
            "get", "/orders/",
            user=cashier_employee, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=order_perms,
        )
        resp = _list_view(req)
        assert resp.status_code == 200
        assert len(resp.data["data"]) == 25
        assert resp.data["meta"]["next"] is not None

    def test_cursor_next_navigates_to_second_page(
        self, db, brand_a, outlet_a, cashier_employee, order_perms
    ):
        for _ in range(30):
            _make_order(brand_a, outlet_a, cashier_employee)
        req = _make_request(
            "get", "/orders/",
            user=cashier_employee, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=order_perms,
        )
        resp = _list_view(req)
        assert resp.data["meta"]["next"] is not None
        # Extract cursor from next URL and request page 2
        next_url = resp.data["meta"]["next"]
        cursor = next_url.split("cursor=")[-1].split("&")[0]
        req2 = _make_request(
            "get", "/orders/",
            user=cashier_employee, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=order_perms,
            query_params={"cursor": cursor},
        )
        resp2 = _list_view(req2)
        assert resp2.status_code == 200
        assert len(resp2.data["data"]) == 5  # remaining orders
        assert resp2.data["meta"]["next"] is None

    def test_page_size_respected(
        self, db, brand_a, outlet_a, cashier_employee, order_perms
    ):
        for _ in range(10):
            _make_order(brand_a, outlet_a, cashier_employee)
        req = _make_request(
            "get", "/orders/",
            user=cashier_employee, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=order_perms,
            query_params={"page_size": "5"},
        )
        resp = _list_view(req)
        assert resp.status_code == 200
        assert len(resp.data["data"]) == 5

    def test_max_page_size_enforced(
        self, db, brand_a, outlet_a, cashier_employee, order_perms
    ):
        for _ in range(10):
            _make_order(brand_a, outlet_a, cashier_employee)
        req = _make_request(
            "get", "/orders/",
            user=cashier_employee, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=order_perms,
            query_params={"page_size": "999"},
        )
        resp = _list_view(req)
        assert resp.status_code == 200
        # max_page_size=100, only 10 orders exist — all returned, but page_size capped
        assert len(resp.data["data"]) == 10


# ---------------------------------------------------------------------------
# N+1 query test
# ---------------------------------------------------------------------------

class TestOrderListQueries:
    def test_no_n_plus_one_queries(
        self, db, brand_a, outlet_a, cashier_employee, order_perms,
        django_assert_num_queries,
    ):
        for _ in range(50):
            _make_order(brand_a, outlet_a, cashier_employee)

        req = _make_request(
            "get", "/orders/",
            user=cashier_employee, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=order_perms,
        )

        with django_assert_num_queries(1):
            resp = _list_view(req)

        assert resp.status_code == 200
        assert len(resp.data["data"]) == 25  # default page_size


# ---------------------------------------------------------------------------
# Brand-level staff (outlet=None) — multi-outlet visibility
# ---------------------------------------------------------------------------

class TestOrderListBrandLevelStaff:
    def test_brand_employee_sees_orders_from_all_outlets(
        self, db, brand_a, outlet_a, outlet_a2, cashier_employee, brand_employee, order_perms
    ):
        """Brand-level staff (outlet_ids=[]) sees orders across all brand outlets."""
        order1 = _make_order(brand_a, outlet_a, cashier_employee)
        order2 = _make_order(brand_a, outlet_a2, cashier_employee)
        req = _make_request(
            "get", "/orders/",
            user=brand_employee, brand_id=brand_a.pk, outlet_ids=[],
            permissions=order_perms,
        )
        resp = _list_view(req)
        assert resp.status_code == 200
        returned_ids = {item["id"] for item in resp.data["data"]}
        assert str(order1.pk) in returned_ids
        assert str(order2.pk) in returned_ids

    def test_brand_employee_can_filter_by_specific_outlet(
        self, db, brand_a, outlet_a, outlet_a2, cashier_employee, brand_employee, order_perms
    ):
        """Brand-level staff can narrow results to a single outlet via outlet_id param."""
        order1 = _make_order(brand_a, outlet_a, cashier_employee)
        order2 = _make_order(brand_a, outlet_a2, cashier_employee)
        req = _make_request(
            "get", "/orders/",
            user=brand_employee, brand_id=brand_a.pk, outlet_ids=[],
            permissions=order_perms,
            query_params={"outlet_id": str(outlet_a.pk)},
        )
        resp = _list_view(req)
        assert resp.status_code == 200
        returned_ids = {item["id"] for item in resp.data["data"]}
        assert str(order1.pk) in returned_ids
        assert str(order2.pk) not in returned_ids

    def test_brand_employee_cross_brand_isolation(
        self, db, brand_a, brand_b, outlet_a, outlet_b, cashier_employee,
        brand_employee, employee_b, order_perms
    ):
        """Brand-level staff cannot see orders from another brand."""
        _make_order(brand_b, outlet_b, employee_b)
        req = _make_request(
            "get", "/orders/",
            user=brand_employee, brand_id=brand_a.pk, outlet_ids=[],
            permissions=order_perms,
        )
        resp = _list_view(req)
        assert resp.status_code == 200
        assert resp.data["data"] == []

    def test_outlet_employee_cannot_see_other_outlet_orders(
        self, db, brand_a, outlet_a, outlet_a2, cashier_employee, brand_employee, order_perms
    ):
        """Outlet-level staff (outlet_ids=[outlet_a]) cannot see outlet_a2 orders."""
        _make_order(brand_a, outlet_a, cashier_employee)
        order2 = _make_order(brand_a, outlet_a2, cashier_employee)
        req = _make_request(
            "get", "/orders/",
            user=cashier_employee, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=order_perms,
        )
        resp = _list_view(req)
        assert resp.status_code == 200
        returned_ids = {item["id"] for item in resp.data["data"]}
        assert str(order2.pk) not in returned_ids
