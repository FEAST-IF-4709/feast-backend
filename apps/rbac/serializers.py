from rest_framework import serializers
from apps.rbac.models import Permission, Role, RolePermission


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["id", "codename", "module", "description"]


class RoleSerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ["id", "brand", "name", "is_system", "permissions"]
        read_only_fields = ["brand", "is_system"]

    def get_permissions(self, obj):
        codenames = obj.rolepermissions.select_related("permission").values_list(
            "permission__codename", flat=True
        )
        return list(codenames)


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
