from rest_framework import serializers
from apps.rbac.models import Permission, Role, RolePermission
from apps.rbac.utils import can_modify_role


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["id", "codename", "module", "description"]


class RoleSerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()
    employee_count = serializers.IntegerField(read_only=True, default=0)
    can_edit_permissions = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ["id", "brand", "name", "is_system", "rank", "employee_count", "permissions", "can_edit_permissions"]
        read_only_fields = ["brand", "is_system", "rank"]

    def get_permissions(self, obj):
        perms = [rp.permission for rp in obj.rolepermissions.select_related("permission")]
        return PermissionSerializer(perms, many=True).data

    def get_can_edit_permissions(self, obj):
        request = self.context.get("request")
        return can_modify_role(request, obj) if request else False


class RoleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["name"]


class RolePermissionUpdateSerializer(serializers.Serializer):
    permission_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=True,
    )

    def validate_permission_ids(self, value):
        existing = set(Permission.objects.filter(id__in=value).values_list("id", flat=True))
        requested = set(value)
        missing = requested - existing
        if missing:
            raise serializers.ValidationError(f"Permission IDs not found: {missing}")
        return value
