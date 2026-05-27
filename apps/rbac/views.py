from rest_framework import status as http_status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied
from django.db import transaction

from core.viewsets.tenant_scoped import TenantScopedViewSet
from core.permissions.has_permission import HasPermission
from core.responses.standard import StandardResponse
from apps.rbac.models import Permission, Role, RolePermission
from apps.rbac.serializers import (
    PermissionSerializer,
    RoleSerializer,
    RoleCreateSerializer,
    RolePermissionUpdateSerializer,
)


class PermissionListView(APIView):
    """GET /api/v1/rbac/permissions/ — returns all permissions (global, no tenant filter)."""

    def get(self, request):
        perms = Permission.objects.all().order_by("module", "codename")
        data = PermissionSerializer(perms, many=True).data
        return StandardResponse(data=list(data), message="Permissions retrieved.", request=request)


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
        return super().get_queryset().prefetch_related("rolepermissions__permission")

    def get_serializer_class(self):
        if self.action == "create":
            return RoleCreateSerializer
        return RoleSerializer

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

    def destroy(self, request, *args, **kwargs):
        role = self.get_object()
        if role.is_system:
            raise PermissionDenied("System roles cannot be deleted.")
        role.delete()
        return StandardResponse(message="Role deleted.", request=request, status=http_status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["put"], url_path="permissions")
    def set_permissions(self, request, pk=None):
        role = self.get_object()
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
