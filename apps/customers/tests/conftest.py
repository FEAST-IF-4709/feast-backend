import pytest
from decimal import Decimal

from apps.customers.models import Customer
from apps.rbac.models import Role
from apps.staff.models import Employee
from apps.tenants.models import Brand, Outlet


@pytest.fixture
def brand_a(db):
    return Brand.objects.create(
        name="Search Brand A", slug="search-brand-a", owner_email="search_a@test.com"
    )


@pytest.fixture
def outlet_a(db, brand_a):
    return Outlet.objects.create(
        brand=brand_a, name="Search Outlet A1",
        address="Jl. Test No. 1",
        latitude=Decimal("-6.200000"), longitude=Decimal("106.800000"),
    )


@pytest.fixture
def cashier_role(db, brand_a):
    return Role.objects.create(brand=brand_a, name="CASHIER", is_system=True)


@pytest.fixture
def cashier_employee(db, brand_a, outlet_a, cashier_role):
    emp = Employee(
        brand=brand_a, outlet=outlet_a, role=cashier_role,
        email="cashier@search.com", full_name="Cashier Search",
    )
    emp.set_password("testpass123")
    emp.save()
    return emp


@pytest.fixture
def customer(db):
    c = Customer(phone="+6281234567890", full_name="Test Customer")
    c.set_password("testpass123")
    c.save()
    return c


@pytest.fixture
def customer_view_perms():
    return frozenset({"customer.view", "cashier.order.create"})
