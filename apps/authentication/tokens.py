from rest_framework_simplejwt.tokens import RefreshToken


def create_employee_tokens(employee) -> dict:
    """Issue a JWT pair for an Employee with full tenant claims."""
    refresh = RefreshToken()

    outlet_ids = [str(employee.outlet_id)] if employee.outlet_id else []

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
