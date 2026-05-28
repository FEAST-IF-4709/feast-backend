import pytest
from decimal import Decimal

from apps.tenants.models import Brand, Outlet
from apps.staff.models import Employee
from apps.customers.models import Customer
from apps.rbac.models import Role
from apps.catalog.models import Category, BrandProduct, OutletProduct
from apps.tables.models import Table
from apps.orders.models import Order


# ---------------------------------------------------------------------------
# Brands
# ---------------------------------------------------------------------------

@pytest.fixture
def brand_a(db):
    return Brand.objects.create(
        name="Brand A",
        slug="brand-a",
        owner_email="owner_a@test.com",
    )


@pytest.fixture
def brand_b(db):
    return Brand.objects.create(
        name="Brand B",
        slug="brand-b",
        owner_email="owner_b@test.com",
    )


# ---------------------------------------------------------------------------
# Outlets
# ---------------------------------------------------------------------------

@pytest.fixture
def outlet_a(db, brand_a):
    return Outlet.objects.create(
        brand=brand_a,
        name="Outlet A1",
        address="Jl. Test No. 1",
        latitude=Decimal("-6.200000"),
        longitude=Decimal("106.800000"),
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


# ---------------------------------------------------------------------------
# Roles (no permissions assigned — tests only need the FK for Employee)
# ---------------------------------------------------------------------------

@pytest.fixture
def kitchen_role(db, brand_a):
    return Role.objects.create(brand=brand_a, name="KITCHEN", is_system=True)


@pytest.fixture
def manager_role(db, brand_a):
    return Role.objects.create(brand=brand_a, name="MANAGER", is_system=True)


@pytest.fixture
def cashier_role(db, brand_a):
    return Role.objects.create(brand=brand_a, name="CASHIER", is_system=True)


# ---------------------------------------------------------------------------
# Employees
# ---------------------------------------------------------------------------

@pytest.fixture
def kitchen_employee(db, brand_a, outlet_a, kitchen_role):
    emp = Employee(
        brand=brand_a,
        outlet=outlet_a,
        role=kitchen_role,
        email="kitchen@test.com",
        full_name="Kitchen Staff",
    )
    emp.set_password("testpass123")
    emp.save()
    return emp


@pytest.fixture
def manager_employee(db, brand_a, outlet_a, manager_role):
    emp = Employee(
        brand=brand_a,
        outlet=outlet_a,
        role=manager_role,
        email="manager@test.com",
        full_name="Manager",
    )
    emp.set_password("testpass123")
    emp.save()
    return emp


@pytest.fixture
def cashier_employee(db, brand_a, outlet_a, cashier_role):
    emp = Employee(
        brand=brand_a,
        outlet=outlet_a,
        role=cashier_role,
        email="cashier@test.com",
        full_name="Cashier",
    )
    emp.set_password("testpass123")
    emp.save()
    return emp


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------

@pytest.fixture
def customer(db):
    c = Customer(phone="+6281234567890", full_name="Test Customer")
    c.set_password("testpass123")
    c.save()
    return c


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------

@pytest.fixture
def table_a(db, outlet_a):
    return Table.objects.create(outlet=outlet_a, label="T1", capacity=4)


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

@pytest.fixture
def category_a(db, brand_a):
    return Category.objects.create(brand=brand_a, name="Makanan")


@pytest.fixture
def brand_product_a(db, brand_a, category_a):
    return BrandProduct.objects.create(
        brand=brand_a,
        category=category_a,
        name="Nasi Goreng",
        base_price=Decimal("25000.00"),
    )


@pytest.fixture
def outlet_product_a(db, outlet_a, brand_product_a):
    return OutletProduct.objects.create(
        brand_product=brand_product_a,
        outlet=outlet_a,
    )


# ---------------------------------------------------------------------------
# Permission frozensets (pure Python — no DB needed in state machine tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def kitchen_perms():
    return frozenset({"kitchen.order.view", "kitchen.order.update_status"})


@pytest.fixture
def manager_perms():
    return frozenset({
        "kitchen.order.view",
        "kitchen.order.update_status",
        "kitchen.order.force_cancel",
    })


# ---------------------------------------------------------------------------
# A minimal settled CASHIER_POS order (used by transition tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def cashier_order(db, brand_a, outlet_a, cashier_employee):
    return Order.objects.create(
        brand=brand_a,
        outlet=outlet_a,
        cashier_employee=cashier_employee,
        order_source=Order.OrderSource.CASHIER_POS,
        payment_method=Order.PaymentMethod.CASH,
        payment_status=Order.PaymentStatus.SETTLED,
        fulfillment_status=Order.FulfillmentStatus.RECEIVED,
        subtotal=Decimal("25000.00"),
        grand_total=Decimal("25000.00"),
    )


# ---------------------------------------------------------------------------
# Additional fixtures for view tests (Phase 6B)
# ---------------------------------------------------------------------------

@pytest.fixture
def cashier_perms():
    return frozenset({"cashier.order.create", "cashier.payment.settle_manual"})


@pytest.fixture
def customer_view_perms():
    return frozenset({"customer.view", "cashier.order.create"})


@pytest.fixture
def outlet_product_out_of_stock(db, outlet_a, brand_product_a):
    return OutletProduct.objects.create(
        brand_product=brand_product_a,
        outlet=outlet_a,
        stock_available=False,
    )


@pytest.fixture
def customer_b(db):
    c = Customer(phone="+6289876543210", full_name="Customer B")
    c.set_password("testpass123")
    c.save()
    return c


@pytest.fixture
def qr_table_order(db, brand_a, outlet_a, customer, table_a):
    """A QR_TABLE order placed by `customer` at `table_a`."""
    return Order.objects.create(
        brand=brand_a,
        outlet=outlet_a,
        customer=customer,
        table=table_a,
        order_source=Order.OrderSource.QR_TABLE,
        payment_status=Order.PaymentStatus.PENDING,
        fulfillment_status=Order.FulfillmentStatus.RECEIVED,
        subtotal=Decimal("25000.00"),
        grand_total=Decimal("25000.00"),
    )
