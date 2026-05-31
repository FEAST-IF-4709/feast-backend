import pytest
from decimal import Decimal

from rest_framework.test import APIRequestFactory, force_authenticate

from apps.tenants.models import Brand, Outlet
from apps.staff.models import Employee
from apps.rbac.models import Role
from apps.orders.models import Order

factory = APIRequestFactory()


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
def outlet_a2(db, brand_a):
    """Second outlet within the same brand as outlet_a (for outlet isolation tests)."""
    return Outlet.objects.create(
        brand=brand_a,
        name="Outlet A2",
        address="Jl. Test No. 3",
        latitude=Decimal("-6.220000"),
        longitude=Decimal("106.820000"),
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
# Roles
# ---------------------------------------------------------------------------

@pytest.fixture
def kitchen_role(db, brand_a):
    return Role.objects.create(brand=brand_a, name="KITCHEN", is_system=True)


@pytest.fixture
def cashier_role(db, brand_a):
    return Role.objects.create(brand=brand_a, name="CASHIER", is_system=True)


@pytest.fixture
def kitchen_role_b(db, brand_b):
    return Role.objects.create(brand=brand_b, name="KITCHEN", is_system=True)


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
# Permission frozensets
# ---------------------------------------------------------------------------

@pytest.fixture
def kitchen_perms():
    return frozenset({"kitchen.order.view", "kitchen.order.update_status"})


@pytest.fixture
def kitchen_perms_with_cancel():
    return frozenset({
        "kitchen.order.view",
        "kitchen.order.update_status",
        "kitchen.order.force_cancel",
    })


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

@pytest.fixture
def settled_order_a(db, brand_a, outlet_a, cashier_employee):
    """Settled RECEIVED order in brand_a / outlet_a."""
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


@pytest.fixture
def pending_order_a(db, brand_a, outlet_a, cashier_employee):
    """Pending RECEIVED order in brand_a / outlet_a (should NOT appear in KDS list)."""
    return Order.objects.create(
        brand=brand_a,
        outlet=outlet_a,
        cashier_employee=cashier_employee,
        order_source=Order.OrderSource.CASHIER_POS,
        payment_method=Order.PaymentMethod.CASH,
        payment_status=Order.PaymentStatus.PENDING,
        fulfillment_status=Order.FulfillmentStatus.RECEIVED,
        subtotal=Decimal("25000.00"),
        grand_total=Decimal("25000.00"),
    )


@pytest.fixture
def settled_order_brand_b(db, brand_b, outlet_b):
    """Settled order belonging to brand_b (cross-brand isolation check)."""
    role_b = Role.objects.create(brand=brand_b, name="CASHIER_B", is_system=True)
    emp_b = Employee(
        brand=brand_b, outlet=outlet_b, role=role_b,
        email="cashier_b@test.com", full_name="Cashier B",
    )
    emp_b.set_password("testpass123")
    emp_b.save()
    return Order.objects.create(
        brand=brand_b,
        outlet=outlet_b,
        cashier_employee=emp_b,
        order_source=Order.OrderSource.CASHIER_POS,
        payment_method=Order.PaymentMethod.CASH,
        payment_status=Order.PaymentStatus.SETTLED,
        fulfillment_status=Order.FulfillmentStatus.RECEIVED,
        subtotal=Decimal("30000.00"),
        grand_total=Decimal("30000.00"),
    )


@pytest.fixture
def settled_order_a2(db, brand_a, outlet_a2, cashier_role):
    """Settled order in brand_a / outlet_a2 (outlet isolation check within same brand)."""
    emp_a2 = Employee(
        brand=brand_a, outlet=outlet_a2, role=cashier_role,
        email="cashier_a2@test.com", full_name="Cashier A2",
    )
    emp_a2.set_password("testpass123")
    emp_a2.save()
    return Order.objects.create(
        brand=brand_a,
        outlet=outlet_a2,
        cashier_employee=emp_a2,
        order_source=Order.OrderSource.CASHIER_POS,
        payment_method=Order.PaymentMethod.CASH,
        payment_status=Order.PaymentStatus.SETTLED,
        fulfillment_status=Order.FulfillmentStatus.RECEIVED,
        subtotal=Decimal("20000.00"),
        grand_total=Decimal("20000.00"),
    )


# ---------------------------------------------------------------------------
# Request factory helper
# ---------------------------------------------------------------------------

def make_request(method, path, data=None, *, user, actor_type, brand_id,
                 outlet_ids, permissions=frozenset()):
    make_fn = getattr(factory, method)
    kwargs = {"format": "json"} if data is not None else {}
    req = make_fn(path, data, **kwargs) if data is not None else make_fn(path)
    req.user = user
    req.tenant = {
        "actor_type": actor_type,
        "brand_id": str(brand_id),
        "outlet_ids": [str(o) for o in outlet_ids],
        "permissions": permissions,
    }
    force_authenticate(req, user=user)
    return req
