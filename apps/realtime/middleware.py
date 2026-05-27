import uuid
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from rest_framework_simplejwt.backends import TokenBackend
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.conf import settings


@database_sync_to_async
def _resolve_token(token_str):
    """
    Validate JWT from WebSocket query string, return (user, tenant_dict).
    Mirrors FeastJWTAuthentication logic but adapted for non-request context.
    """
    if not token_str:
        return None, None

    try:
        backend = TokenBackend(
            algorithm=settings.SIMPLE_JWT.get("ALGORITHM", "HS256"),
            signing_key=settings.SIMPLE_JWT.get("SIGNING_KEY", settings.SECRET_KEY),
        )
        payload = backend.decode(token_str, verify=True)
    except (InvalidToken, TokenError, Exception):
        return None, None

    jti = payload.get("jti")
    if jti:
        from apps.authentication.models import BlacklistedJTI
        if BlacklistedJTI.objects.filter(jti=jti).exists():
            return None, None

    actor_type = payload.get("actor_type")
    user_id = payload.get("user_id")
    if not actor_type or not user_id:
        return None, None

    try:
        if actor_type == "EMPLOYEE":
            from apps.staff.models import Employee
            user = Employee.objects.select_related("brand", "outlet", "role").get(
                pk=user_id, is_active=True
            )
        elif actor_type == "CUSTOMER":
            from apps.customers.models import Customer
            user = Customer.objects.get(pk=user_id, is_active=True)
        else:
            return None, None
    except Exception:
        return None, None

    brand_id = payload.get("brand_id")
    outlet_id = payload.get("outlet_id")
    outlet_ids_raw = payload.get("outlet_ids", [])
    role_id = payload.get("role_id")
    permissions = payload.get("permissions", [])

    try:
        outlet_ids = [uuid.UUID(oid) for oid in outlet_ids_raw if oid]
    except (ValueError, AttributeError):
        outlet_ids = []

    tenant = {
        "brand_id": uuid.UUID(brand_id) if brand_id else None,
        "outlet_id": uuid.UUID(outlet_id) if outlet_id else None,
        "outlet_ids": outlet_ids,
        "role_id": uuid.UUID(role_id) if role_id else None,
        "permissions": frozenset(permissions),
        "actor_type": actor_type,
    }

    return user, tenant


class JWTAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode("utf-8")
        params = parse_qs(query_string)
        token_str = params.get("token", [None])[0]

        user, tenant = await _resolve_token(token_str)
        scope["user"] = user
        scope["tenant"] = tenant

        return await self.inner(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(inner)
