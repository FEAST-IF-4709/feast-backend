"""Tests for Brand model extension and GET/PATCH /api/v1/brands/me/ endpoint."""
import pytest
from decimal import Decimal
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.tenants.models import Brand, Outlet, get_default_operating_hours
from apps.staff.models import Employee
from apps.rbac.models import Role
from apps.tenants.views import BrandProfileViewSet

factory = APIRequestFactory()


# ---------------------------------------------------------------------------
# Fixtures
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


@pytest.fixture
def owner_role_a(db, brand_a):
    return Role.objects.create(brand=brand_a, name="BRAND_OWNER", is_system=True)


@pytest.fixture
def owner_role_b(db, brand_b):
    return Role.objects.create(brand=brand_b, name="BRAND_OWNER", is_system=True)


@pytest.fixture
def employee_a(db, brand_a, outlet_a, owner_role_a):
    emp = Employee(
        brand=brand_a,
        outlet=outlet_a,
        role=owner_role_a,
        email="owner_a@test.com",
        full_name="Owner A",
    )
    emp.set_password("testpass123")
    emp.save()
    return emp


@pytest.fixture
def employee_b(db, brand_b, outlet_b, owner_role_b):
    emp = Employee(
        brand=brand_b,
        outlet=outlet_b,
        role=owner_role_b,
        email="owner_b@test.com",
        full_name="Owner B",
    )
    emp.set_password("testpass123")
    emp.save()
    return emp


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_request(method, path, data=None, *, user, brand_id, outlet_ids,
                  permissions=frozenset()):
    make_fn = getattr(factory, method)
    req = make_fn(path, data, format="json") if data is not None else make_fn(path)
    req.user = user
    req.tenant = {
        "actor_type": "EMPLOYEE",
        "brand_id": str(brand_id),
        "outlet_ids": [str(o) for o in outlet_ids],
        "permissions": permissions,
    }
    force_authenticate(req, user=user)
    return req


_me_view = BrandProfileViewSet.as_view({"get": "me", "patch": "me"})


# ---------------------------------------------------------------------------
# Model default value tests
# ---------------------------------------------------------------------------

class TestBrandDefaults:
    def test_new_fields_default_values(self, brand_a):
        brand_a.refresh_from_db()
        assert brand_a.description == ""
        assert brand_a.phone == ""
        assert brand_a.cuisine_type == ""
        assert brand_a.logo_url == ""
        assert brand_a.location_address == ""
        assert brand_a.operating_hours == get_default_operating_hours()

    def test_operating_hours_default_has_all_days(self, brand_a):
        expected_days = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
        assert set(brand_a.operating_hours.keys()) == expected_days

    def test_existing_fields_unchanged(self, brand_a):
        assert brand_a.name == "Brand A"
        assert brand_a.slug == "brand-a"
        assert brand_a.owner_email == "owner_a@test.com"
        assert brand_a.subscription_status == Brand.SubscriptionStatus.TRIAL
        assert brand_a.is_active is True


# ---------------------------------------------------------------------------
# GET /api/v1/brands/me/
# ---------------------------------------------------------------------------

class TestGetBrandsMe:
    def test_returns_200_with_all_fields(self, employee_a, brand_a, outlet_a):
        req = _make_request(
            "get", "/brands/me/",
            user=employee_a, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
        )
        resp = _me_view(req)
        assert resp.status_code == 200
        data = resp.data["data"]
        expected_keys = {
            "id", "name", "slug", "owner_email", "subscription_status", "is_active",
            "description", "phone", "cuisine_type", "logo_url", "location_address",
            "operating_hours", "created_at", "updated_at",
        }
        assert expected_keys.issubset(data.keys())

    def test_returns_correct_brand_for_tenant(self, employee_a, brand_a, outlet_a):
        brand_a.description = "Test desc"
        brand_a.save()
        req = _make_request(
            "get", "/brands/me/",
            user=employee_a, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
        )
        resp = _me_view(req)
        assert resp.data["data"]["description"] == "Test desc"
        assert resp.data["data"]["name"] == "Brand A"


# ---------------------------------------------------------------------------
# PATCH /api/v1/brands/me/
# ---------------------------------------------------------------------------

class TestPatchBrandsMe:
    def test_update_description(self, employee_a, brand_a, outlet_a):
        req = _make_request(
            "patch", "/brands/me/", {"description": "Warung kopi terbaik"},
            user=employee_a, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=frozenset({"brand.update"}),
        )
        resp = _me_view(req)
        assert resp.status_code == 200
        brand_a.refresh_from_db()
        assert brand_a.description == "Warung kopi terbaik"

    def test_update_cuisine_type_and_location(self, employee_a, brand_a, outlet_a):
        req = _make_request(
            "patch", "/brands/me/",
            {"cuisine_type": "Indonesian", "location_address": "Jl. Sudirman No. 1"},
            user=employee_a, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=frozenset({"brand.update"}),
        )
        resp = _me_view(req)
        assert resp.status_code == 200
        brand_a.refresh_from_db()
        assert brand_a.cuisine_type == "Indonesian"
        assert brand_a.location_address == "Jl. Sudirman No. 1"

    def test_patch_phone_valid_plus62(self, employee_a, brand_a, outlet_a):
        req = _make_request(
            "patch", "/brands/me/", {"phone": "+6281234567890"},
            user=employee_a, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=frozenset({"brand.update"}),
        )
        resp = _me_view(req)
        assert resp.status_code == 200
        brand_a.refresh_from_db()
        assert brand_a.phone == "+6281234567890"

    def test_patch_phone_valid_08(self, employee_a, brand_a, outlet_a):
        req = _make_request(
            "patch", "/brands/me/", {"phone": "081234567890"},
            user=employee_a, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=frozenset({"brand.update"}),
        )
        resp = _me_view(req)
        assert resp.status_code == 200
        brand_a.refresh_from_db()
        assert brand_a.phone == "081234567890"

    def test_patch_phone_invalid_format(self, employee_a, brand_a, outlet_a):
        req = _make_request(
            "patch", "/brands/me/", {"phone": "1234567890"},
            user=employee_a, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=frozenset({"brand.update"}),
        )
        resp = _me_view(req)
        assert resp.status_code == 400

    def test_patch_phone_empty_string_accepted(self, employee_a, brand_a, outlet_a):
        req = _make_request(
            "patch", "/brands/me/", {"phone": ""},
            user=employee_a, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=frozenset({"brand.update"}),
        )
        resp = _me_view(req)
        assert resp.status_code == 200

    def test_patch_operating_hours_valid(self, employee_a, brand_a, outlet_a):
        valid_hours = {
            "mon": {"open": "09:00", "close": "21:00"},
            "fri": {"open": "10:00", "close": "23:00"},
        }
        req = _make_request(
            "patch", "/brands/me/", {"operating_hours": valid_hours},
            user=employee_a, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=frozenset({"brand.update"}),
        )
        resp = _me_view(req)
        assert resp.status_code == 200
        brand_a.refresh_from_db()
        assert brand_a.operating_hours["mon"]["open"] == "09:00"

    def test_patch_operating_hours_invalid_day_key(self, employee_a, brand_a, outlet_a):
        req = _make_request(
            "patch", "/brands/me/",
            {"operating_hours": {"monday": {"open": "08:00", "close": "22:00"}}},
            user=employee_a, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=frozenset({"brand.update"}),
        )
        resp = _me_view(req)
        assert resp.status_code == 400

    def test_patch_operating_hours_missing_close_key(self, employee_a, brand_a, outlet_a):
        req = _make_request(
            "patch", "/brands/me/",
            {"operating_hours": {"mon": {"open": "08:00"}}},
            user=employee_a, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=frozenset({"brand.update"}),
        )
        resp = _me_view(req)
        assert resp.status_code == 400

    def test_patch_operating_hours_invalid_time_format(self, employee_a, brand_a, outlet_a):
        req = _make_request(
            "patch", "/brands/me/",
            {"operating_hours": {"mon": {"open": "8:00", "close": "22:00"}}},
            user=employee_a, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=frozenset({"brand.update"}),
        )
        resp = _me_view(req)
        assert resp.status_code == 400

    def test_patch_logo_url(self, employee_a, brand_a, outlet_a):
        req = _make_request(
            "patch", "/brands/me/",
            {"logo_url": "https://cdn.example.com/logo.png"},
            user=employee_a, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=frozenset({"brand.update"}),
        )
        resp = _me_view(req)
        assert resp.status_code == 200
        brand_a.refresh_from_db()
        assert brand_a.logo_url == "https://cdn.example.com/logo.png"

    def test_patch_read_only_fields_are_ignored(self, employee_a, brand_a, outlet_a):
        req = _make_request(
            "patch", "/brands/me/",
            {"name": "Hacked Name", "slug": "hacked", "owner_email": "hacked@x.com",
             "description": "legit update"},
            user=employee_a, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=frozenset({"brand.update"}),
        )
        resp = _me_view(req)
        assert resp.status_code == 200
        brand_a.refresh_from_db()
        assert brand_a.name == "Brand A"
        assert brand_a.slug == "brand-a"
        assert brand_a.owner_email == "owner_a@test.com"
        assert brand_a.description == "legit update"


# ---------------------------------------------------------------------------
# Permission enforcement
# ---------------------------------------------------------------------------

class TestBrandPermissions:
    def test_patch_without_brand_update_permission_returns_403(
        self, employee_a, brand_a, outlet_a
    ):
        req = _make_request(
            "patch", "/brands/me/", {"description": "no permission"},
            user=employee_a, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=frozenset({"kitchen.order.view"}),
        )
        resp = _me_view(req)
        assert resp.status_code == 403

    def test_patch_with_empty_permissions_returns_403(self, employee_a, brand_a, outlet_a):
        req = _make_request(
            "patch", "/brands/me/", {"description": "no permission"},
            user=employee_a, brand_id=brand_a.pk, outlet_ids=[outlet_a.pk],
            permissions=frozenset(),
        )
        resp = _me_view(req)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Cross-tenant isolation
# ---------------------------------------------------------------------------

class TestCrossTenantIsolation:
    def test_employee_b_gets_brand_b_profile(
        self, employee_a, employee_b, brand_a, brand_b, outlet_a, outlet_b
    ):
        brand_a.description = "Brand A description"
        brand_a.save()
        brand_b.description = "Brand B description"
        brand_b.save()

        req = _make_request(
            "get", "/brands/me/",
            user=employee_b, brand_id=brand_b.pk, outlet_ids=[outlet_b.pk],
        )
        resp = _me_view(req)
        assert resp.status_code == 200
        assert resp.data["data"]["description"] == "Brand B description"
        assert resp.data["data"]["name"] == "Brand B"

    def test_employee_b_patch_does_not_affect_brand_a(
        self, employee_a, employee_b, brand_a, brand_b, outlet_a, outlet_b
    ):
        brand_a.description = "Original A"
        brand_a.save()

        req = _make_request(
            "patch", "/brands/me/", {"description": "Modified by B"},
            user=employee_b, brand_id=brand_b.pk, outlet_ids=[outlet_b.pk],
            permissions=frozenset({"brand.update"}),
        )
        _me_view(req)

        brand_a.refresh_from_db()
        assert brand_a.description == "Original A"
