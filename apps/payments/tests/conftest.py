from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.tenants.models import Brand, Outlet
from apps.staff.models import Employee
from apps.rbac.models import Role
from apps.orders.models import Order
from apps.payments.models import PaymentTransaction


@pytest.fixture
def brand(db):
    return Brand.objects.create(
        name="Test Brand",
        slug="test-brand",
        owner_email="owner@test.com",
    )


@pytest.fixture
def outlet(db, brand):
    return Outlet.objects.create(
        brand=brand,
        name="Test Outlet",
        address="Jl. Test No. 1",
        latitude=Decimal("-6.200000"),
        longitude=Decimal("106.800000"),
    )


@pytest.fixture
def cashier_role(db, brand):
    return Role.objects.create(brand=brand, name="CASHIER", is_system=True)


@pytest.fixture
def cashier_emp(db, brand, outlet, cashier_role):
    emp = Employee(
        brand=brand,
        outlet=outlet,
        role=cashier_role,
        email="cashier@test.com",
        full_name="Cashier",
    )
    emp.set_password("testpass123")
    emp.save()
    return emp


@pytest.fixture
def pending_qris_order(db, brand, outlet):
    return Order.objects.create(
        brand=brand,
        outlet=outlet,
        order_source=Order.OrderSource.QR_TABLE,
        payment_method=Order.PaymentMethod.QRIS_MIDTRANS,
        payment_status=Order.PaymentStatus.PENDING,
        subtotal=Decimal("75000.00"),
        grand_total=Decimal("75000.00"),
    )


@pytest.fixture
def qris_payment_transaction(db, pending_qris_order):
    """Active PaymentTransaction for pending_qris_order, midtrans_order_id = order_number."""
    return PaymentTransaction.objects.create(
        order=pending_qris_order,
        midtrans_order_id=pending_qris_order.order_number,
        transaction_id="txn-test-001",
        payment_type="qris",
        gross_amount=pending_qris_order.grand_total,
        qr_string="00020101test",
        qr_image_url="https://example.com/qr.png",
        expires_at=timezone.now() + timedelta(minutes=15),
        transaction_status="pending",
        raw_request_payload={},
        raw_response_payload={},
    )


@pytest.fixture
def pending_cash_order(db, brand, outlet, cashier_emp):
    return Order.objects.create(
        brand=brand,
        outlet=outlet,
        cashier_employee=cashier_emp,
        order_source=Order.OrderSource.CASHIER_POS,
        payment_method=Order.PaymentMethod.CASH,
        payment_status=Order.PaymentStatus.PENDING,
        subtotal=Decimal("50000.00"),
        grand_total=Decimal("50000.00"),
    )


@pytest.fixture
def pending_edc_order(db, brand, outlet, cashier_emp):
    return Order.objects.create(
        brand=brand,
        outlet=outlet,
        cashier_employee=cashier_emp,
        order_source=Order.OrderSource.CASHIER_POS,
        payment_method=Order.PaymentMethod.EDC,
        payment_status=Order.PaymentStatus.PENDING,
        subtotal=Decimal("50000.00"),
        grand_total=Decimal("50000.00"),
    )


_factory = APIRequestFactory()


def make_customer_request(method, url, data=None, *, user):
    fn = getattr(_factory, method)
    req = fn(url, data, format="json") if data is not None else fn(url)
    req.user = user
    req.tenant = {"actor_type": "CUSTOMER"}
    force_authenticate(req, user=user)
    return req


def make_employee_request(method, url, data=None, *, user, brand_id, outlet_ids, permissions=frozenset()):
    fn = getattr(_factory, method)
    req = fn(url, data, format="json") if data is not None else fn(url)
    req.user = user
    req.tenant = {
        "actor_type": "EMPLOYEE",
        "brand_id": str(brand_id),
        "outlet_ids": [str(o) for o in outlet_ids],
        "permissions": permissions,
    }
    force_authenticate(req, user=user)
    return req


def make_webhook_request(data):
    return _factory.post("/webhook/midtrans/", data, format="json")
