"""Tests for core.utils.state_machine and Order.apply_fulfillment_transition."""
import pytest
from django.core.exceptions import PermissionDenied, ValidationError

from apps.orders.models import Order, OrderStatusHistory
from core.utils.state_machine import FULFILLMENT_TRANSITIONS, validate_transition


# ---------------------------------------------------------------------------
# validate_transition — pure unit tests (no DB)
# ---------------------------------------------------------------------------

class TestValidTransitions:
    @pytest.mark.parametrize(
        "from_s, to_s",
        [
            ("RECEIVED", "IN_PROGRESS"),
            ("RECEIVED", "CANCELLED"),
            ("IN_PROGRESS", "READY"),
            ("IN_PROGRESS", "CANCELLED"),
            ("READY", "SERVED"),
            ("SERVED", "COMPLETED"),
        ],
    )
    def test_valid_path(self, from_s, to_s, manager_perms):
        validate_transition(from_s, to_s, manager_perms)  # must not raise


class TestInvalidTransitions:
    @pytest.mark.parametrize(
        "from_s, to_s",
        [
            ("RECEIVED", "READY"),       # skip
            ("RECEIVED", "SERVED"),      # skip
            ("RECEIVED", "COMPLETED"),   # skip
            ("IN_PROGRESS", "SERVED"),   # skip
            ("IN_PROGRESS", "COMPLETED"),# skip
            ("READY", "RECEIVED"),       # backward
            ("SERVED", "RECEIVED"),      # backward
            ("COMPLETED", "RECEIVED"),   # terminal
            ("COMPLETED", "IN_PROGRESS"),# terminal
            ("CANCELLED", "RECEIVED"),   # terminal
            ("CANCELLED", "IN_PROGRESS"),# terminal
        ],
    )
    def test_invalid_path_raises(self, from_s, to_s):
        with pytest.raises(ValidationError) as exc_info:
            validate_transition(from_s, to_s)
        assert exc_info.value.code == "STATE_TRANSITION_INVALID"


class TestPermissionGatedTransitions:
    def test_in_progress_to_cancelled_without_perm_raises(self, kitchen_perms):
        with pytest.raises(PermissionDenied) as exc_info:
            validate_transition("IN_PROGRESS", "CANCELLED", kitchen_perms)
        assert "kitchen.order.force_cancel" in str(exc_info.value)

    def test_in_progress_to_cancelled_with_force_cancel_perm(self, manager_perms):
        validate_transition("IN_PROGRESS", "CANCELLED", manager_perms)  # must not raise

    def test_received_to_cancelled_no_special_perm_needed(self):
        # RECEIVED→CANCELLED requires no specific permission — any actor may cancel
        validate_transition("RECEIVED", "CANCELLED", frozenset())

    def test_received_to_in_progress_no_special_perm_needed(self, kitchen_perms):
        validate_transition("RECEIVED", "IN_PROGRESS", kitchen_perms)

    def test_empty_perms_still_validates_allowed_path(self):
        validate_transition("READY", "SERVED", frozenset())


# ---------------------------------------------------------------------------
# Order.apply_fulfillment_transition — integration with DB
# ---------------------------------------------------------------------------

class TestApplyFulfillmentTransition:
    def test_valid_transition_updates_status(self, cashier_order, manager_perms):
        cashier_order.apply_fulfillment_transition(
            "IN_PROGRESS",
            changed_by=None,
            actor_permissions=manager_perms,
        )
        cashier_order.refresh_from_db()
        assert cashier_order.fulfillment_status == "IN_PROGRESS"

    def test_writes_history_row(self, cashier_order, manager_perms):
        cashier_order.apply_fulfillment_transition(
            "IN_PROGRESS",
            actor_permissions=manager_perms,
        )
        history = OrderStatusHistory.objects.filter(order=cashier_order).order_by("changed_at")
        assert history.count() == 1
        row = history.first()
        assert row.from_status == "RECEIVED"
        assert row.to_status == "IN_PROGRESS"

    def test_history_records_changed_by(self, cashier_order, kitchen_employee, kitchen_perms):
        cashier_order.apply_fulfillment_transition(
            "IN_PROGRESS",
            changed_by=kitchen_employee,
            actor_permissions=kitchen_perms,
        )
        row = OrderStatusHistory.objects.get(order=cashier_order)
        assert row.changed_by_id == kitchen_employee.pk

    def test_invalid_transition_raises_and_does_not_save(self, cashier_order):
        with pytest.raises(ValidationError):
            cashier_order.apply_fulfillment_transition("COMPLETED")
        cashier_order.refresh_from_db()
        assert cashier_order.fulfillment_status == "RECEIVED"  # unchanged

    def test_missing_force_cancel_perm_raises_and_does_not_save(self, cashier_order, kitchen_perms):
        # Advance to IN_PROGRESS first
        cashier_order.apply_fulfillment_transition("IN_PROGRESS", actor_permissions=kitchen_perms)
        cashier_order.refresh_from_db()

        with pytest.raises(PermissionDenied):
            cashier_order.apply_fulfillment_transition("CANCELLED", actor_permissions=kitchen_perms)
        cashier_order.refresh_from_db()
        assert cashier_order.fulfillment_status == "IN_PROGRESS"  # unchanged

    def test_multiple_transitions_chain(self, cashier_order, kitchen_perms, manager_perms):
        steps = [
            ("IN_PROGRESS", kitchen_perms),
            ("READY", kitchen_perms),
            ("SERVED", kitchen_perms),
            ("COMPLETED", kitchen_perms),
        ]
        for to_status, perms in steps:
            cashier_order.apply_fulfillment_transition(to_status, actor_permissions=perms)

        cashier_order.refresh_from_db()
        assert cashier_order.fulfillment_status == "COMPLETED"
        assert OrderStatusHistory.objects.filter(order=cashier_order).count() == len(steps)


# ---------------------------------------------------------------------------
# FULFILLMENT_TRANSITIONS dict integrity
# ---------------------------------------------------------------------------

class TestTransitionsDict:
    def test_all_statuses_have_entry(self):
        statuses = {s.value for s in Order.FulfillmentStatus}
        assert statuses == set(FULFILLMENT_TRANSITIONS.keys())

    def test_targets_are_valid_statuses(self):
        statuses = {s.value for s in Order.FulfillmentStatus}
        for targets in FULFILLMENT_TRANSITIONS.values():
            for t in targets:
                assert t in statuses
