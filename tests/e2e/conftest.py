"""
Shared fixtures for E2E order flow tests.

These create the full tenant context needed to exercise the FEAST API end-to-end
using real JWT tokens and the real URL router (APIClient).
"""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.authentication.tokens import create_customer_tokens, create_employee_tokens
from apps.catalog.models import BrandProduct, Category, OutletProduct
from apps.customers.models import Customer
from apps.orders.models import Order, OrderItem
from apps.rbac.models import Permission, Role, RolePermission
from apps.staff.models import Employee
from apps.tables.models import Table
from apps.tenants.models import Brand, Outlet


# ---------------------------------------------------------------------------
# Tenant core
# ---------------------------------------------------------------------------

@pytest.fixture
def brand(db):
    return Brand.objects.create(name="FEAST Demo Brand", slug="feast-demo", owner_email="owner@feast.test")


@pytest.fixture
def outlet(db, brand):
    return Outlet.objects.create(
        brand=brand,
        name="Main Outlet",
        address="Jl. Sudirman No. 1, Jakarta",
        latitude=Decimal("-6.200000"),
        longitude=Decimal("106.800000"),
    )


# ---------------------------------------------------------------------------
# Roles with real DB permissions (needed for JWT claim resolution)
# ---------------------------------------------------------------------------

@pytest.fixture
def perm_kitchen_view(db):
    p, _ = Permission.objects.get_or_create(codename="kitchen.order.view", defaults={"module": "kitchen", "description": ""})
    return p


@pytest.fixture
def perm_kitchen_update(db):
    p, _ = Permission.objects.get_or_create(codename="kitchen.order.update_status", defaults={"module": "kitchen", "description": ""})
    return p


@pytest.fixture
def perm_kitchen_cancel(db):
    p, _ = Permission.objects.get_or_create(codename="kitchen.order.force_cancel", defaults={"module": "kitchen", "description": ""})
    return p


@pytest.fixture
def perm_cashier_create(db):
    p, _ = Permission.objects.get_or_create(codename="cashier.order.create", defaults={"module": "cashier", "description": ""})
    return p


@pytest.fixture
def perm_cashier_settle(db):
    p, _ = Permission.objects.get_or_create(codename="cashier.payment.settle_manual", defaults={"module": "cashier", "description": ""})
    return p


@pytest.fixture
def kitchen_role(db, brand, perm_kitchen_view, perm_kitchen_update, perm_kitchen_cancel):
    role = Role.objects.create(brand=brand, name="KITCHEN", is_system=True)
    RolePermission.objects.bulk_create([
        RolePermission(role=role, permission=perm_kitchen_view),
        RolePermission(role=role, permission=perm_kitchen_update),
        RolePermission(role=role, permission=perm_kitchen_cancel),
    ])
    return role


@pytest.fixture
def cashier_role(db, brand, perm_cashier_create, perm_cashier_settle):
    role = Role.objects.create(brand=brand, name="CASHIER", is_system=True)
    RolePermission.objects.bulk_create([
        RolePermission(role=role, permission=perm_cashier_create),
        RolePermission(role=role, permission=perm_cashier_settle),
    ])
    return role


# ---------------------------------------------------------------------------
# Employees
# ---------------------------------------------------------------------------

@pytest.fixture
def kitchen_employee(db, brand, outlet, kitchen_role):
    emp = Employee(brand=brand, outlet=outlet, role=kitchen_role, email="kitchen@feast.test", full_name="Kitchen Staff")
    emp.set_password("testpass123")
    emp.save()
    return emp


@pytest.fixture
def cashier_employee(db, brand, outlet, cashier_role):
    emp = Employee(brand=brand, outlet=outlet, role=cashier_role, email="cashier@feast.test", full_name="Cashier")
    emp.set_password("testpass123")
    emp.save()
    return emp


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------

@pytest.fixture
def customer(db):
    c = Customer(phone="+6281234500001", full_name="E2E Customer", email="customer@feast.test")
    c.set_password("testpass123")
    c.save()
    return c


# ---------------------------------------------------------------------------
# Catalog + Table
# ---------------------------------------------------------------------------

@pytest.fixture
def category(db, brand):
    return Category.objects.create(brand=brand, name="Makanan Utama")


@pytest.fixture
def brand_product(db, brand, category):
    return BrandProduct.objects.create(
        brand=brand, category=category, name="Nasi Goreng Spesial", base_price=Decimal("35000.00")
    )


@pytest.fixture
def outlet_product(db, outlet, brand_product):
    return OutletProduct.objects.create(brand_product=brand_product, outlet=outlet, stock_available=True)


@pytest.fixture
def table(db, outlet):
    return Table.objects.create(outlet=outlet, label="T-01", capacity=4)


# ---------------------------------------------------------------------------
# Pre-settled order (for kitchen lifecycle tests that don't test order creation)
# ---------------------------------------------------------------------------

@pytest.fixture
def settled_order(db, brand, outlet, customer, table, outlet_product):
    order = Order.objects.create(
        brand=brand,
        outlet=outlet,
        customer=customer,
        table=table,
        order_source=Order.OrderSource.QR_TABLE,
        payment_status=Order.PaymentStatus.SETTLED,
        fulfillment_status=Order.FulfillmentStatus.RECEIVED,
        subtotal=Decimal("35000.00"),
        grand_total=Decimal("35000.00"),
    )
    OrderItem.objects.create(
        order=order,
        outlet_product=outlet_product,
        product_snapshot={"name": "Nasi Goreng Spesial", "price": "35000.00"},
        quantity=1,
        unit_price=Decimal("35000.00"),
        line_total=Decimal("35000.00"),
    )
    return order


# ---------------------------------------------------------------------------
# Authenticated API clients (real JWT, real URL routing)
# ---------------------------------------------------------------------------

@pytest.fixture
def kitchen_client(kitchen_employee):
    tokens = create_employee_tokens(kitchen_employee)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


@pytest.fixture
def cashier_client(cashier_employee):
    tokens = create_employee_tokens(cashier_employee)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


@pytest.fixture
def customer_client(customer):
    tokens = create_customer_tokens(customer)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


@pytest.fixture
def anon_client():
    return APIClient()
