"""Tests for Phase 9: Kitchen Display System endpoints."""
from unittest.mock import patch

import pytest

from apps.orders.models import Order, OrderStatusHistory
from apps.kitchen.views import (
    KitchenOrderCancelView,
    KitchenOrderListView,
    KitchenOrderStatusUpdateView,
)
from .conftest import make_request


# ---------------------------------------------------------------------------
# GET /api/v1/kitchen/orders/
# ---------------------------------------------------------------------------

class TestKitchenOrderList:
    def test_brand_isolation(
        self, db, kitchen_employee, brand_a, outlet_a,
        settled_order_a, settled_order_brand_b, kitchen_perms,
    ):
        """Kitchen staff of brand_a must NOT see orders belonging to brand_b."""
        req = make_request(
            "get", "/kitchen/orders/",
            user=kitchen_employee, actor_type="EMPLOYEE",
            brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=kitchen_perms,
        )
        resp = KitchenOrderListView.as_view()(req)
        assert resp.status_code == 200
        ids_returned = [item["id"] for item in resp.data["data"]]
        assert str(settled_order_a.pk) in ids_returned
        assert str(settled_order_brand_b.pk) not in ids_returned

    def test_outlet_isolation(
        self, db, kitchen_employee, brand_a, outlet_a, outlet_a2,
        settled_order_a, settled_order_a2, kitchen_perms,
    ):
        """Kitchen staff scoped to outlet_a must NOT see orders from outlet_a2
        even though both outlets belong to the same brand."""
        req = make_request(
            "get", "/kitchen/orders/",
            user=kitchen_employee, actor_type="EMPLOYEE",
            brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],  # scoped to outlet_a only
            permissions=kitchen_perms,
        )
        resp = KitchenOrderListView.as_view()(req)
        assert resp.status_code == 200
        ids_returned = [item["id"] for item in resp.data["data"]]
        assert str(settled_order_a.pk) in ids_returned
        assert str(settled_order_a2.pk) not in ids_returned

    def test_pending_payment_excluded(
        self, db, kitchen_employee, brand_a, outlet_a,
        settled_order_a, pending_order_a, kitchen_perms,
    ):
        """Orders with payment_status=PENDING must NEVER appear in the KDS list."""
        req = make_request(
            "get", "/kitchen/orders/",
            user=kitchen_employee, actor_type="EMPLOYEE",
            brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=kitchen_perms,
        )
        resp = KitchenOrderListView.as_view()(req)
        assert resp.status_code == 200
        ids_returned = [item["id"] for item in resp.data["data"]]
        assert str(settled_order_a.pk) in ids_returned
        assert str(pending_order_a.pk) not in ids_returned

    def test_missing_view_permission_returns_403(
        self, db, kitchen_employee, brand_a, outlet_a,
    ):
        req = make_request(
            "get", "/kitchen/orders/",
            user=kitchen_employee, actor_type="EMPLOYEE",
            brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=frozenset(),  # no permissions
        )
        resp = KitchenOrderListView.as_view()(req)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /api/v1/kitchen/orders/{pk}/status/
# ---------------------------------------------------------------------------

class TestKitchenOrderStatusUpdate:
    @patch("apps.kitchen.views._broadcast_status_change")
    @patch("apps.kitchen.views.transaction.on_commit", side_effect=lambda f: f())
    def test_received_to_in_progress_success(
        self, _mock_commit, mock_broadcast,
        db, kitchen_employee, brand_a, outlet_a,
        settled_order_a, kitchen_perms,
    ):
        """PATCH RECEIVED → IN_PROGRESS returns 200, inserts history row, fires WS broadcast."""
        req = make_request(
            "patch", f"/kitchen/orders/{settled_order_a.pk}/status/",
            {"to_status": "IN_PROGRESS"},
            user=kitchen_employee, actor_type="EMPLOYEE",
            brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=kitchen_perms,
        )
        resp = KitchenOrderStatusUpdateView.as_view()(req, pk=settled_order_a.pk)
        assert resp.status_code == 200

        settled_order_a.refresh_from_db()
        assert settled_order_a.fulfillment_status == Order.FulfillmentStatus.IN_PROGRESS

        history = OrderStatusHistory.objects.filter(order=settled_order_a)
        assert history.count() == 1
        row = history.first()
        assert row.from_status == Order.FulfillmentStatus.RECEIVED
        assert row.to_status == Order.FulfillmentStatus.IN_PROGRESS

        mock_broadcast.assert_called_once_with(
            str(outlet_a.pk),
            str(settled_order_a.pk),
            "IN_PROGRESS",
        )

    def test_invalid_transition_returns_409(
        self, db, kitchen_employee, brand_a, outlet_a,
        settled_order_a, kitchen_perms,
    ):
        """PATCH RECEIVED → READY (skipping IN_PROGRESS) must return 409."""
        req = make_request(
            "patch", f"/kitchen/orders/{settled_order_a.pk}/status/",
            {"to_status": "READY"},
            user=kitchen_employee, actor_type="EMPLOYEE",
            brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=kitchen_perms,
        )
        resp = KitchenOrderStatusUpdateView.as_view()(req, pk=settled_order_a.pk)
        assert resp.status_code == 409
        assert resp.data["code"] == "STATE_TRANSITION_INVALID"

        # Status must remain unchanged
        settled_order_a.refresh_from_db()
        assert settled_order_a.fulfillment_status == Order.FulfillmentStatus.RECEIVED

    def test_missing_update_permission_returns_403(
        self, db, kitchen_employee, brand_a, outlet_a, settled_order_a,
    ):
        req = make_request(
            "patch", f"/kitchen/orders/{settled_order_a.pk}/status/",
            {"to_status": "IN_PROGRESS"},
            user=kitchen_employee, actor_type="EMPLOYEE",
            brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=frozenset({"kitchen.order.view"}),  # missing update_status
        )
        resp = KitchenOrderStatusUpdateView.as_view()(req, pk=settled_order_a.pk)
        assert resp.status_code == 403

    def test_pending_order_cannot_update_status(
        self, db, kitchen_employee, brand_a, outlet_a,
        pending_order_a, kitchen_perms,
    ):
        req = make_request(
            "patch", f"/kitchen/orders/{pending_order_a.pk}/status/",
            {"to_status": "IN_PROGRESS"},
            user=kitchen_employee, actor_type="EMPLOYEE",
            brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=kitchen_perms,
        )
        resp = KitchenOrderStatusUpdateView.as_view()(req, pk=pending_order_a.pk)
        assert resp.status_code == 400

    def test_cross_brand_order_not_found(
        self, db, kitchen_employee, brand_a, outlet_a,
        settled_order_brand_b, kitchen_perms,
    ):
        req = make_request(
            "patch", f"/kitchen/orders/{settled_order_brand_b.pk}/status/",
            {"to_status": "IN_PROGRESS"},
            user=kitchen_employee, actor_type="EMPLOYEE",
            brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=kitchen_perms,
        )
        resp = KitchenOrderStatusUpdateView.as_view()(req, pk=settled_order_brand_b.pk)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/kitchen/orders/{pk}/cancel/
# ---------------------------------------------------------------------------

class TestKitchenOrderCancel:
    def test_cancel_without_force_cancel_permission_returns_403(
        self, db, kitchen_employee, brand_a, outlet_a,
        settled_order_a, kitchen_perms,
    ):
        """Employee without kitchen.order.force_cancel must receive 403 regardless of order state."""
        req = make_request(
            "post", f"/kitchen/orders/{settled_order_a.pk}/cancel/",
            {"cancel_reason": "Test reason"},
            user=kitchen_employee, actor_type="EMPLOYEE",
            brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=kitchen_perms,  # missing force_cancel
        )
        resp = KitchenOrderCancelView.as_view()(req, pk=settled_order_a.pk)
        assert resp.status_code == 403

        # Verify order was NOT cancelled
        settled_order_a.refresh_from_db()
        assert settled_order_a.fulfillment_status == Order.FulfillmentStatus.RECEIVED

    @patch("apps.kitchen.views._broadcast_cancel")
    @patch("apps.kitchen.views.transaction.on_commit", side_effect=lambda f: f())
    def test_cancel_received_order_success(
        self, _mock_commit, mock_broadcast,
        db, kitchen_employee, brand_a, outlet_a,
        settled_order_a, kitchen_perms_with_cancel,
    ):
        """Employee with force_cancel can cancel a RECEIVED order; history row inserted."""
        req = make_request(
            "post", f"/kitchen/orders/{settled_order_a.pk}/cancel/",
            {"cancel_reason": "Customer changed mind"},
            user=kitchen_employee, actor_type="EMPLOYEE",
            brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=kitchen_perms_with_cancel,
        )
        resp = KitchenOrderCancelView.as_view()(req, pk=settled_order_a.pk)
        assert resp.status_code == 200

        settled_order_a.refresh_from_db()
        assert settled_order_a.fulfillment_status == Order.FulfillmentStatus.CANCELLED

        history = OrderStatusHistory.objects.filter(order=settled_order_a)
        assert history.count() == 1
        row = history.first()
        assert row.to_status == Order.FulfillmentStatus.CANCELLED
        assert row.notes == "Customer changed mind"

        mock_broadcast.assert_called_once()

    def test_cancel_missing_reason_returns_400(
        self, db, kitchen_employee, brand_a, outlet_a,
        settled_order_a, kitchen_perms_with_cancel,
    ):
        req = make_request(
            "post", f"/kitchen/orders/{settled_order_a.pk}/cancel/",
            {"cancel_reason": ""},
            user=kitchen_employee, actor_type="EMPLOYEE",
            brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=kitchen_perms_with_cancel,
        )
        resp = KitchenOrderCancelView.as_view()(req, pk=settled_order_a.pk)
        assert resp.status_code == 400
        assert resp.data["code"] == "VALIDATION_ERROR"

    @patch("apps.kitchen.views._broadcast_cancel")
    @patch("apps.kitchen.views.transaction.on_commit", side_effect=lambda f: f())
    def test_cancel_in_progress_order_with_force_cancel(
        self, _mock_commit, mock_broadcast,
        db, kitchen_employee, brand_a, outlet_a,
        settled_order_a, kitchen_perms_with_cancel,
    ):
        """Employee with force_cancel can cancel an IN_PROGRESS order (state machine allows it)."""
        # Advance to IN_PROGRESS first
        settled_order_a.fulfillment_status = Order.FulfillmentStatus.IN_PROGRESS
        settled_order_a.save(update_fields=["fulfillment_status"])

        req = make_request(
            "post", f"/kitchen/orders/{settled_order_a.pk}/cancel/",
            {"cancel_reason": "Equipment failure"},
            user=kitchen_employee, actor_type="EMPLOYEE",
            brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=kitchen_perms_with_cancel,
        )
        resp = KitchenOrderCancelView.as_view()(req, pk=settled_order_a.pk)
        assert resp.status_code == 200

        settled_order_a.refresh_from_db()
        assert settled_order_a.fulfillment_status == Order.FulfillmentStatus.CANCELLED
