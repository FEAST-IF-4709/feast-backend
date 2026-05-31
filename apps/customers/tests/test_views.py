"""Tests for customer staff-side search endpoint."""
import urllib.parse

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.customers.views import CustomerSearchView

factory = APIRequestFactory()


def _search_request(phone, *, user, brand_id, outlet_ids, permissions=frozenset()):
    """Build a GET request to /customers/search/ with the given phone param."""
    qs = urllib.parse.urlencode({"phone": phone})
    req = factory.get(f"/customers/search/?{qs}")
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
# GET /api/v1/customers/search/?phone=...
# ---------------------------------------------------------------------------

class TestCustomerSearchView:
    def test_finds_customer_by_exact_phone(self, db, cashier_employee, customer,
                                            brand_a, outlet_a, customer_view_perms):
        req = _search_request(
            customer.phone,
            user=cashier_employee, brand_id=brand_a.pk,
            outlet_ids=[outlet_a.pk], permissions=customer_view_perms,
        )
        resp = CustomerSearchView.as_view()(req)
        assert resp.status_code == 200
        assert resp.data["data"]["phone"] == customer.phone
        assert resp.data["data"]["full_name"] == customer.full_name
        assert "id" in resp.data["data"]

    def test_not_found_returns_404(self, db, cashier_employee, brand_a, outlet_a,
                                    customer_view_perms):
        req = _search_request(
            "08000000000",
            user=cashier_employee, brand_id=brand_a.pk,
            outlet_ids=[outlet_a.pk], permissions=customer_view_perms,
        )
        resp = CustomerSearchView.as_view()(req)
        assert resp.status_code == 404

    def test_requires_employee_auth(self, db, customer, brand_a):
        req = factory.get(f"/customers/search/?phone={customer.phone}")
        req.user = customer
        req.tenant = {"actor_type": "CUSTOMER"}
        force_authenticate(req, user=customer)
        resp = CustomerSearchView.as_view()(req)
        assert resp.status_code == 403

    def test_requires_customer_view_permission(self, db, cashier_employee, brand_a, outlet_a):
        req = _search_request(
            "08000000000",
            user=cashier_employee, brand_id=brand_a.pk,
            outlet_ids=[outlet_a.pk],
            permissions=frozenset(),
        )
        resp = CustomerSearchView.as_view()(req)
        assert resp.status_code == 403

    def test_phone_param_required(self, db, cashier_employee, brand_a, outlet_a,
                                   customer_view_perms):
        req = factory.get("/customers/search/")
        req.user = cashier_employee
        req.tenant = {
            "actor_type": "EMPLOYEE",
            "brand_id": str(brand_a.pk),
            "outlet_ids": [str(outlet_a.pk)],
            "permissions": customer_view_perms,
        }
        force_authenticate(req, cashier_employee)
        resp = CustomerSearchView.as_view()(req)
        assert resp.status_code == 400
