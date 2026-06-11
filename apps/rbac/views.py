from collections import defaultdict

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status as http_status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count

from core.viewsets.tenant_scoped import TenantScopedViewSet
from core.permissions.has_permission import HasPermission
from core.responses.standard import StandardResponse
from core.schema import COMMON_ERROR_RESPONSES
from apps.rbac.models import Permission, Role, RolePermission
from apps.rbac.utils import can_modify_role
from apps.rbac.serializers import (
    PermissionSerializer,
    RoleSerializer,
    RoleCreateSerializer,
    RolePermissionUpdateSerializer,
)


class PermissionListView(APIView):
    """GET /api/v1/rbac/permissions/ — returns all permissions (global, no tenant filter).

    Query params:
      ?grouped=true  →  returns [{module, permissions: [...]}] grouped by module
    """

    permission_classes = [HasPermission]
    required_permissions = {"get": "rbac.role.view"}

    @extend_schema(
        tags=["RBAC"],
        summary="List all permissions",
        description=(
            "Returns the full catalogue of permissions available to assign to roles. "
            "Add `?grouped=true` to receive permissions grouped by module."
        ),
        responses={200: PermissionSerializer(many=True), **COMMON_ERROR_RESPONSES},
    )
    def get(self, request):
        perms = Permission.objects.all().order_by("module", "codename")

        if request.query_params.get("grouped") == "true":
            grouped: dict[str, list] = defaultdict(list)
            for perm in perms:
                grouped[perm.module].append(PermissionSerializer(perm).data)
            data = [{"module": module, "permissions": items} for module, items in grouped.items()]
            return StandardResponse(data=data, message="Permissions retrieved.", request=request)

        data = PermissionSerializer(perms, many=True).data
        return StandardResponse(data=list(data), message="Permissions retrieved.", request=request)


@extend_schema_view(
    list=extend_schema(tags=["RBAC"], summary="List roles", responses={200: RoleSerializer(many=True), **COMMON_ERROR_RESPONSES}),
    retrieve=extend_schema(tags=["RBAC"], summary="Get role", responses={200: RoleSerializer, **COMMON_ERROR_RESPONSES}),
    create=extend_schema(tags=["RBAC"], summary="Create role", request=RoleCreateSerializer, responses={201: RoleSerializer, **COMMON_ERROR_RESPONSES}),
    update=extend_schema(tags=["RBAC"], summary="Update role", request=RoleCreateSerializer, responses={200: RoleSerializer, **COMMON_ERROR_RESPONSES}),
    partial_update=extend_schema(tags=["RBAC"], summary="Partial update role", responses={200: RoleSerializer, **COMMON_ERROR_RESPONSES}),
    destroy=extend_schema(tags=["RBAC"], summary="Delete role", description="System roles cannot be deleted.", responses={204: None, **COMMON_ERROR_RESPONSES}),
)
class RoleViewSet(TenantScopedViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [HasPermission]
    tenant_field = "brand"
    outlet_field = None

    required_permissions = {
        "list": "rbac.role.view",
        "retrieve": "rbac.role.view",
        "create": "rbac.role.create",
        "update": "rbac.role.update",
        "partial_update": "rbac.role.update",
        "destroy": "rbac.role.delete",
        "set_permissions": "rbac.role.update",
    }

    def get_queryset(self):
        return (
            super().get_queryset()
            .prefetch_related("rolepermissions__permission")
            .annotate(employee_count=Count("employees"))
        )

    def get_serializer_class(self):
        if self.action == "create":
            return RoleCreateSerializer
        return RoleSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        data = RoleSerializer(queryset, many=True, context={"request": request}).data
        return StandardResponse(data=list(data), message="Roles retrieved.", request=request)

    def retrieve(self, request, *args, **kwargs):
        role = self.get_object()
        return StandardResponse(
            data=RoleSerializer(role, context={"request": request}).data,
            message="Role retrieved.",
            request=request,
        )

    def create(self, request, *args, **kwargs):
        serializer = RoleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = serializer.save(brand_id=request.tenant["brand_id"])
        return StandardResponse(
            data=RoleSerializer(role).data,
            message="Role created.",
            request=request,
            status=http_status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        role = self.get_object()
        if not can_modify_role(request, role):
            raise PermissionDenied("Insufficient hierarchy to rename this role.")
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        role = self.get_object()
        if not can_modify_role(request, role):
            raise PermissionDenied("Insufficient hierarchy to rename this role.")
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        role = self.get_object()
        if role.is_system:
            raise PermissionDenied("System roles cannot be deleted.")
        role.delete()
        return StandardResponse(message="Role deleted.", request=request, status=http_status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["RBAC"],
        summary="Set role permissions",
        description="Replace all permissions on a role with the provided list. Requires `rbac.role.update` permission. System roles cannot be modified.",
        request=RolePermissionUpdateSerializer,
        responses={200: RoleSerializer, **COMMON_ERROR_RESPONSES},
    )
    @action(detail=True, methods=["put"], url_path="permissions")
    def set_permissions(self, request, pk=None):
        role = self.get_object()
        if not can_modify_role(request, role):
            raise PermissionDenied("Insufficient hierarchy to modify this role's permissions.")

        serializer = RolePermissionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        permission_ids = serializer.validated_data["permission_ids"]

        with transaction.atomic():
            role.rolepermissions.all().delete()
            RolePermission.objects.bulk_create([
                RolePermission(role=role, permission_id=pid)
                for pid in permission_ids
            ])

        role.refresh_from_db()
        return StandardResponse(
            data=RoleSerializer(role).data,
            message="Role permissions updated.",
            request=request,
        )
