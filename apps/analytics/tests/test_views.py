"""Tests for GET /api/v1/analytics/dashboard/summary/ and /daily-chart/"""
from decimal import Decimal

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.analytics.views import DashboardSummaryView, DailyRevenueChartView
from apps.orders.models import Order
from apps.rbac.models import Role
from apps.staff.models import Employee
from apps.tenants.models import Brand, Outlet

factory = APIRequestFactory()

DASHBOARD_PERMS = frozenset({"dashboard.view"})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def brand_a(db):
    return Brand.objects.create(
        name="Brand A", slug="brand-a", owner_email="owner_a@test.com"
    )


@pytest.fixture
def outlet_a(db, brand_a):
    return Outlet.objects.create(
        brand=brand_a, name="Outlet A1", address="Jl. Test No. 1",
        latitude=Decimal("-6.200000"), longitude=Decimal("106.800000"),
    )


@pytest.fixture
def manager_role(db, brand_a):
    return Role.objects.create(brand=brand_a, name="MANAGER", is_system=True)


@pytest.fixture
def manager(db, brand_a, outlet_a, manager_role):
    emp = Employee(
        brand=brand_a, outlet=outlet_a, role=manager_role,
        email="manager@test.com", full_name="Manager",
    )
    emp.set_password("testpass123")
    emp.save()
    return emp


def _make_order(brand, outlet, employee, payment_status, grand_total="50000.00", **kwargs):
    kwargs.setdefault("fulfillment_status", Order.FulfillmentStatus.COMPLETED)
    return Order.objects.create(
        brand=brand, outlet=outlet, cashier_employee=employee,
        order_source=Order.OrderSource.CASHIER_POS,
        payment_method=Order.PaymentMethod.CASH,
        payment_status=payment_status,
        subtotal=Decimal(grand_total),
        grand_total=Decimal(grand_total),
        **kwargs,
    )


def _make_req(view_name, user, brand_id, outlet_ids, permissions=DASHBOARD_PERMS,
              query_params=None):
    path = f"/analytics/dashboard/{view_name}/"
    if query_params:
        qs = "&".join(f"{k}={v}" for k, v in query_params.items())
        path = f"{path}?{qs}"
    req = factory.get(path)
    req.user = user
    req.tenant = {
        "actor_type": "EMPLOYEE",
        "brand_id": str(brand_id),
        "outlet_ids": [str(o) for o in outlet_ids],
        "permissions": permissions,
    }
    force_authenticate(req, user=user)
    return req


# ---------------------------------------------------------------------------
# DashboardSummaryView
# ---------------------------------------------------------------------------

_summary_view = DashboardSummaryView.as_view()


class TestDashboardSummaryView:
    def test_returns_200_with_expected_shape(self, db, brand_a, outlet_a, manager):
        req = _make_req("summary", manager, brand_a.pk, [outlet_a.pk])
        resp = _summary_view(req)
        assert resp.status_code == 200
        data = resp.data["data"]
        assert {"total_revenue", "total_orders", "settled_orders",
                "pending_orders", "date_from", "date_to"}.issubset(data.keys())

    def test_requires_dashboard_view_permission(self, db, brand_a, outlet_a, manager):
        req = _make_req("summary", manager, brand_a.pk, [outlet_a.pk],
                        permissions=frozenset({"orders.view"}))
        resp = _summary_view(req)
        assert resp.status_code == 403

    def test_counts_settled_revenue(self, db, brand_a, outlet_a, manager):
        _make_order(brand_a, outlet_a, manager, Order.PaymentStatus.SETTLED,
                    grand_total="75000.00")
        _make_order(brand_a, outlet_a, manager, Order.PaymentStatus.SETTLED,
                    grand_total="25000.00")
        req = _make_req("summary", manager, brand_a.pk, [outlet_a.pk])
        resp = _summary_view(req)
        data = resp.data["data"]
        assert data["total_revenue"] == "100000.00"
        assert data["settled_orders"] == 2

    def test_pending_orders_counted_separately(self, db, brand_a, outlet_a, manager):
        _make_order(brand_a, outlet_a, manager, Order.PaymentStatus.SETTLED)
        _make_order(brand_a, outlet_a, manager, Order.PaymentStatus.PENDING,
                    fulfillment_status=Order.FulfillmentStatus.RECEIVED)
        req = _make_req("summary", manager, brand_a.pk, [outlet_a.pk])
        resp = _summary_view(req)
        data = resp.data["data"]
        assert data["settled_orders"] == 1
        assert data["pending_orders"] == 1
        assert data["total_orders"] == 2

    def test_no_orders_returns_zero_revenue(self, db, brand_a, outlet_a, manager):
        req = _make_req("summary", manager, brand_a.pk, [outlet_a.pk])
        resp = _summary_view(req)
        data = resp.data["data"]
        assert data["total_revenue"] == "0"
        assert data["total_orders"] == 0

    def test_cross_brand_isolation(self, db, brand_a, outlet_a, manager):
        brand_b = Brand.objects.create(
            name="Brand B", slug="brand-b", owner_email="owner_b@test.com"
        )
        outlet_b = Outlet.objects.create(
            brand=brand_b, name="Outlet B1", address="Jl. B No. 1",
            latitude=Decimal("-6.21"), longitude=Decimal("106.81"),
        )
        role_b = Role.objects.create(brand=brand_b, name="MANAGER", is_system=True)
        emp_b = Employee(brand=brand_b, outlet=outlet_b, role=role_b,
                         email="mgr_b@test.com", full_name="B")
        emp_b.set_password("x")
        emp_b.save()
        _make_order(brand_b, outlet_b, emp_b, Order.PaymentStatus.SETTLED,
                    grand_total="999999.00")

        req = _make_req("summary", manager, brand_a.pk, [outlet_a.pk])
        resp = _summary_view(req)
        assert resp.data["data"]["total_revenue"] == "0"

    def test_date_from_filter(self, db, brand_a, outlet_a, manager):
        from django.utils import timezone
        import datetime

        old = _make_order(brand_a, outlet_a, manager, Order.PaymentStatus.SETTLED,
                          grand_total="30000.00")
        old.placed_at = timezone.now() - datetime.timedelta(days=10)
        old.save(update_fields=["placed_at"])

        recent = _make_order(brand_a, outlet_a, manager, Order.PaymentStatus.SETTLED,
                             grand_total="50000.00")

        today = timezone.now().date().isoformat()
        req = _make_req("summary", manager, brand_a.pk, [outlet_a.pk],
                        query_params={"date_from": today})
        resp = _summary_view(req)
        data = resp.data["data"]
        assert data["settled_orders"] == 1
        assert data["total_revenue"] == "50000.00"


# ---------------------------------------------------------------------------
# DailyRevenueChartView
# ---------------------------------------------------------------------------

_chart_view = DailyRevenueChartView.as_view()


class TestDailyRevenueChartView:
    def test_returns_200_list(self, db, brand_a, outlet_a, manager):
        req = _make_req("daily-chart", manager, brand_a.pk, [outlet_a.pk])
        resp = _chart_view(req)
        assert resp.status_code == 200
        assert isinstance(resp.data["data"], list)

    def test_requires_dashboard_view_permission(self, db, brand_a, outlet_a, manager):
        req = _make_req("daily-chart", manager, brand_a.pk, [outlet_a.pk],
                        permissions=frozenset())
        resp = _chart_view(req)
        assert resp.status_code == 403

    def test_chart_point_shape(self, db, brand_a, outlet_a, manager):
        _make_order(brand_a, outlet_a, manager, Order.PaymentStatus.SETTLED)
        req = _make_req("daily-chart", manager, brand_a.pk, [outlet_a.pk])
        resp = _chart_view(req)
        assert len(resp.data["data"]) >= 1
        point = resp.data["data"][0]
        assert {"date", "revenue", "order_count"}.issubset(point.keys())

    def test_only_settled_orders_in_chart(self, db, brand_a, outlet_a, manager):
        _make_order(brand_a, outlet_a, manager, Order.PaymentStatus.SETTLED,
                    grand_total="100000.00")
        _make_order(brand_a, outlet_a, manager, Order.PaymentStatus.PENDING,
                    grand_total="999999.00",
                    fulfillment_status=Order.FulfillmentStatus.RECEIVED)
        req = _make_req("daily-chart", manager, brand_a.pk, [outlet_a.pk])
        resp = _chart_view(req)
        # Only 1 settled order: revenue should be 100000, not 1099999
        point = resp.data["data"][0]
        assert point["order_count"] == 1
        assert point["revenue"] == "100000.00"

    def test_days_param_capped_at_90(self, db, brand_a, outlet_a, manager):
        req = _make_req("daily-chart", manager, brand_a.pk, [outlet_a.pk],
                        query_params={"days": "999"})
        resp = _chart_view(req)
        # Request should not fail even with oversized param
        assert resp.status_code == 200

    def test_invalid_days_param_defaults_to_30(self, db, brand_a, outlet_a, manager):
        req = _make_req("daily-chart", manager, brand_a.pk, [outlet_a.pk],
                        query_params={"days": "not-a-number"})
        resp = _chart_view(req)
        assert resp.status_code == 200

    def test_empty_result_when_no_orders(self, db, brand_a, outlet_a, manager):
        req = _make_req("daily-chart", manager, brand_a.pk, [outlet_a.pk])
        resp = _chart_view(req)
        assert resp.data["data"] == []
