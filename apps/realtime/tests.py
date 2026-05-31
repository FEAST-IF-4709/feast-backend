from decimal import Decimal

import pytest
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from apps.authentication.tokens import create_customer_tokens, create_employee_tokens
from apps.customers.models import Customer
from apps.rbac.models import Permission, Role, RolePermission
from apps.staff.models import Employee
from apps.tenants.models import Brand, Outlet
from core.asgi import application


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def brand(db):
    return Brand.objects.create(
        name="RT Brand", slug="rt-brand", owner_email="rt@test.com"
    )


@pytest.fixture
def outlet(db, brand):
    return Outlet.objects.create(
        brand=brand,
        name="RT Outlet A",
        address="Jl. Test 1",
        latitude=Decimal("-6.200000"),
        longitude=Decimal("106.800000"),
    )


@pytest.fixture
def other_outlet(db, brand):
    return Outlet.objects.create(
        brand=brand,
        name="RT Outlet B",
        address="Jl. Test 2",
        latitude=Decimal("-6.201000"),
        longitude=Decimal("106.801000"),
    )


@pytest.fixture
def kitchen_perm(db):
    return Permission.objects.create(codename="kitchen.order.view", module="kitchen")


@pytest.fixture
def kitchen_role(db, brand, kitchen_perm):
    role = Role.objects.create(brand=brand, name="KITCHEN")
    RolePermission.objects.create(role=role, permission=kitchen_perm)
    return role


@pytest.fixture
def kitchen_employee(db, brand, outlet, kitchen_role):
    emp = Employee(
        brand=brand,
        outlet=outlet,
        role=kitchen_role,
        email="kitchen@test.com",
        full_name="Kitchen Staff",
    )
    emp.set_password("pass")
    emp.save()
    return emp


@pytest.fixture
def customer(db):
    c = Customer(phone="+6281234567890", full_name="Test Customer")
    c.set_password("pass")
    c.save()
    return c


@pytest.fixture
def kitchen_token(kitchen_employee):
    return create_employee_tokens(kitchen_employee)["access"]


@pytest.fixture
def customer_token(customer):
    return create_customer_tokens(customer)["access"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
async def test_kitchen_connect_valid_employee_accepted(outlet, kitchen_token):
    comm = WebsocketCommunicator(application, f"ws/kitchen/{outlet.id}/?token={kitchen_token}")
    connected, _ = await comm.connect()
    assert connected is True
    await comm.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_kitchen_connect_customer_token_rejected(outlet, customer_token):
    comm = WebsocketCommunicator(application, f"ws/kitchen/{outlet.id}/?token={customer_token}")
    connected, _ = await comm.connect()
    assert connected is False


@pytest.mark.django_db(transaction=True)
async def test_kitchen_connect_wrong_outlet_rejected(other_outlet, kitchen_token):
    # Employee's outlet_ids = [outlet.id], connecting to other_outlet → 4403
    comm = WebsocketCommunicator(application, f"ws/kitchen/{other_outlet.id}/?token={kitchen_token}")
    connected, _ = await comm.connect()
    assert connected is False


@pytest.mark.django_db(transaction=True)
async def test_kitchen_broadcast_received_by_all_subscribers(outlet, kitchen_token):
    url = f"ws/kitchen/{outlet.id}/?token={kitchen_token}"
    comm1 = WebsocketCommunicator(application, url)
    comm2 = WebsocketCommunicator(application, url)

    connected1, _ = await comm1.connect()
    connected2, _ = await comm2.connect()
    assert connected1 is True
    assert connected2 is True

    channel_layer = get_channel_layer()
    payload = {"order_id": "test-uuid", "action": "ORDER_CREATED"}
    await channel_layer.group_send(
        f"outlet.{outlet.id}.kitchen",
        {"type": "order_created", "payload": payload},
    )

    msg1 = await comm1.receive_json_from()
    msg2 = await comm2.receive_json_from()

    assert msg1["event"] == "order.created"
    assert msg1["data"] == payload
    assert msg2["event"] == "order.created"
    assert msg2["data"] == payload

    await comm1.disconnect()
    await comm2.disconnect()
