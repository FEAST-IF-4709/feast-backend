import uuid
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework.exceptions import AuthenticationFailed

from apps.authentication.models import BlacklistedJTI


class FeastJWTAuthentication(JWTAuthentication):
    """
    Custom JWT authentication that resolves request.user to Employee or Customer
    based on the actor_type claim. Also populates request.tenant at auth time
    so middleware doesn't need to run after DRF.
    """

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None

        user, validated_token = result
        self._attach_tenant(request, validated_token)
        return user, validated_token

    def _attach_tenant(self, request, token):
        try:
            brand_id = token.get("brand_id")
            outlet_id = token.get("outlet_id")
            outlet_ids_raw = token.get("outlet_ids", [])
            role_id = token.get("role_id")
            role_rank = token.get("role_rank")
            permissions = token.get("permissions", [])
            actor_type = token.get("actor_type", "EMPLOYEE")

            outlet_ids = [uuid.UUID(oid) for oid in outlet_ids_raw if oid]

            request.tenant = {
                "brand_id": uuid.UUID(brand_id) if brand_id else None,
                "outlet_id": uuid.UUID(outlet_id) if outlet_id else None,
                "outlet_ids": outlet_ids,
                "role_id": uuid.UUID(role_id) if role_id else None,
                "role_rank": int(role_rank) if role_rank is not None else None,
                "permissions": frozenset(permissions),
                "actor_type": actor_type,
            }
        except (TypeError, ValueError, AttributeError):
            request.tenant = None

    def get_validated_token(self, raw_token):
        token = super().get_validated_token(raw_token)

        jti = token.get("jti")
        if jti and BlacklistedJTI.objects.filter(jti=jti).exists():
            raise InvalidToken("Token has been blacklisted.")

        return token

    def get_user(self, validated_token):
        actor_type = validated_token.get("actor_type")
        user_id = validated_token.get("user_id")

        if not actor_type or not user_id:
            raise AuthenticationFailed("Token missing actor_type or user_id claim.")

        try:
            if actor_type == "EMPLOYEE":
                from apps.staff.models import Employee
                return (
                    Employee.objects.select_related("brand", "outlet", "role")
                    .get(pk=user_id, is_active=True)
                )
            elif actor_type == "CUSTOMER":
                from apps.customers.models import Customer
                return Customer.objects.get(pk=user_id, is_active=True)
            else:
                raise AuthenticationFailed(f"Unknown actor_type: {actor_type}")
        except AuthenticationFailed:
            raise
        except Exception as exc:
            raise AuthenticationFailed("User not found or inactive.") from exc
