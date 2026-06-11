from rest_framework.permissions import BasePermission


class HasPermission(BasePermission):
    """
    Checks that request.tenant["permissions"] contains the required codename
    declared in view.required_permissions[view.action].
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return False
        action = getattr(view, "action", request.method.lower())
        required = getattr(view, "required_permissions", {}).get(action)
        if required is None:
            return True
        return required in tenant["permissions"]
