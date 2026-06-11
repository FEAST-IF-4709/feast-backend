from apps.tenants.models import Outlet
from rest_framework_simplejwt.tokens import RefreshToken


def create_superadmin_tokens(superadmin) -> dict:
    """Issue a JWT pair for a SuperAdmin with actor_type=SUPERADMIN and no brand/outlet scope."""
    refresh = RefreshToken()
    refresh["user_id"] = str(superadmin.id)
    refresh["actor_type"] = "SUPERADMIN"
    refresh["full_name"] = superadmin.full_name
    refresh["email"] = superadmin.email
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def create_employee_tokens(employee) -> dict:
    """Issue a JWT pair for an Employee with full tenant claims."""
    refresh = RefreshToken()

    if employee.outlet_id:
        # Outlet-level staff → scoped to their one outlet
        outlet_ids = [str(employee.outlet_id)]
    else:
        # Brand-level employee (owner/manager) → all outlets of the brand
        outlet_ids = [
            str(oid)
            for oid in Outlet.objects.filter(brand_id=employee.brand_id)
            .values_list("id", flat=True)
        ]

    permissions = list(
        employee.role.rolepermissions.select_related("permission")
        .values_list("permission__codename", flat=True)
    )

    refresh["user_id"] = str(employee.id)
    refresh["actor_type"] = "EMPLOYEE"
    refresh["brand_id"] = str(employee.brand_id)
    refresh["outlet_id"] = str(employee.outlet_id) if employee.outlet_id else None
    refresh["outlet_ids"] = outlet_ids
    refresh["role_id"] = str(employee.role_id)
    refresh["role_rank"] = employee.role.rank  # None for custom roles
    refresh["permissions"] = permissions

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def create_customer_tokens(customer) -> dict:
    """Issue a JWT pair for a Customer."""
    refresh = RefreshToken()

    refresh["user_id"] = str(customer.id)
    refresh["actor_type"] = "CUSTOMER"

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }
