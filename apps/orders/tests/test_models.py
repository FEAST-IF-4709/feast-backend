"""Tests for Order.clean() source matrix and OrderItem computed fields."""
import uuid
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.orders.models import Order, OrderItem


# ---------------------------------------------------------------------------
# Helpers: build an unsaved Order without hitting the DB
# ---------------------------------------------------------------------------

def _make_order(**kwargs) -> Order:
    """Return an unsaved Order instance with sensible defaults."""
    defaults = dict(
        brand_id=uuid.uuid4(),
        outlet_id=uuid.uuid4(),
        customer_id=None,
        table_id=None,
        cashier_employee_id=None,
        order_source=Order.OrderSource.CASHIER_POS,
        payment_method=Order.PaymentMethod.CASH,
        grand_total=Decimal("0"),
    )
    defaults.update(kwargs)
    return Order(**defaults)


# ---------------------------------------------------------------------------
# QR_TABLE source
# ---------------------------------------------------------------------------

class TestQRTableSource:
    def test_valid(self):
        order = _make_order(
            order_source=Order.OrderSource.QR_TABLE,
            customer_id=uuid.uuid4(),
            table_id=uuid.uuid4(),
            cashier_employee_id=None,
        )
        order.clean()  # must not raise

    def test_missing_customer_raises(self):
        order = _make_order(
            order_source=Order.OrderSource.QR_TABLE,
            customer_id=None,
            table_id=uuid.uuid4(),
        )
        with pytest.raises(ValidationError) as exc_info:
            order.clean()
        assert "customer" in exc_info.value.message_dict

    def test_missing_table_raises(self):
        order = _make_order(
            order_source=Order.OrderSource.QR_TABLE,
            customer_id=uuid.uuid4(),
            table_id=None,
        )
        with pytest.raises(ValidationError) as exc_info:
            order.clean()
        assert "table" in exc_info.value.message_dict

    def test_cashier_present_raises(self):
        order = _make_order(
            order_source=Order.OrderSource.QR_TABLE,
            customer_id=uuid.uuid4(),
            table_id=uuid.uuid4(),
            cashier_employee_id=uuid.uuid4(),
        )
        with pytest.raises(ValidationError) as exc_info:
            order.clean()
        assert "cashier_employee" in exc_info.value.message_dict


# ---------------------------------------------------------------------------
# CASHIER_POS source
# ---------------------------------------------------------------------------

class TestCashierPOSSource:
    def test_valid_walk_in_no_customer(self):
        order = _make_order(
            order_source=Order.OrderSource.CASHIER_POS,
            cashier_employee_id=uuid.uuid4(),
            customer_id=None,
            table_id=None,
        )
        order.clean()

    def test_valid_with_customer(self):
        order = _make_order(
            order_source=Order.OrderSource.CASHIER_POS,
            cashier_employee_id=uuid.uuid4(),
            customer_id=uuid.uuid4(),
        )
        order.clean()

    def test_valid_with_table(self):
        order = _make_order(
            order_source=Order.OrderSource.CASHIER_POS,
            cashier_employee_id=uuid.uuid4(),
            table_id=uuid.uuid4(),
        )
        order.clean()

    def test_missing_cashier_raises(self):
        order = _make_order(
            order_source=Order.OrderSource.CASHIER_POS,
            cashier_employee_id=None,
        )
        with pytest.raises(ValidationError) as exc_info:
            order.clean()
        assert "cashier_employee" in exc_info.value.message_dict


# ---------------------------------------------------------------------------
# MOBILE_APP_DELIVERY source
# ---------------------------------------------------------------------------

class TestMobileDeliverySource:
    def test_valid(self):
        order = _make_order(
            order_source=Order.OrderSource.MOBILE_APP_DELIVERY,
            customer_id=uuid.uuid4(),
            table_id=None,
            cashier_employee_id=None,
        )
        order.clean()

    def test_missing_customer_raises(self):
        order = _make_order(
            order_source=Order.OrderSource.MOBILE_APP_DELIVERY,
            customer_id=None,
        )
        with pytest.raises(ValidationError) as exc_info:
            order.clean()
        assert "customer" in exc_info.value.message_dict

    def test_table_present_raises(self):
        order = _make_order(
            order_source=Order.OrderSource.MOBILE_APP_DELIVERY,
            customer_id=uuid.uuid4(),
            table_id=uuid.uuid4(),
        )
        with pytest.raises(ValidationError) as exc_info:
            order.clean()
        assert "table" in exc_info.value.message_dict

    def test_cashier_present_raises(self):
        order = _make_order(
            order_source=Order.OrderSource.MOBILE_APP_DELIVERY,
            customer_id=uuid.uuid4(),
            cashier_employee_id=uuid.uuid4(),
        )
        with pytest.raises(ValidationError) as exc_info:
            order.clean()
        assert "cashier_employee" in exc_info.value.message_dict


# ---------------------------------------------------------------------------
# OrderItem computed line_total
# ---------------------------------------------------------------------------

class TestOrderItemLineTotalComputed:
    def test_line_total_set_on_save(self, db, cashier_order):
        item = OrderItem(
            order=cashier_order,
            product_snapshot={"name": "Nasi Goreng", "base_price": "25000.00"},
            quantity=3,
            unit_price=Decimal("25000.00"),
            line_total=Decimal("0"),  # will be overwritten by save()
        )
        item.save()
        item.refresh_from_db()
        assert item.line_total == Decimal("75000.00")

    def test_line_total_updates_on_resave(self, db, cashier_order):
        item = OrderItem.objects.create(
            order=cashier_order,
            product_snapshot={"name": "Es Teh"},
            quantity=2,
            unit_price=Decimal("5000.00"),
            line_total=Decimal("0"),
        )
        item.quantity = 5
        item.save(update_fields=["quantity", "line_total"])
        item.refresh_from_db()
        assert item.line_total == Decimal("25000.00")
