from rest_framework import serializers
from .models import Employee
from apps.rbac.models import Role
from apps.tenants.models import Outlet


class EmployeeSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.name", read_only=True)
    outlet_name = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            "id", "brand_id", "outlet_id", "outlet_name",
            "role_id", "role_name", "email", "full_name",
            "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "brand_id", "created_at", "updated_at"]

    def get_outlet_name(self, obj):
        return obj.outlet.name if obj.outlet else None


def _validate_role(value, request):
    if request and hasattr(request, "tenant") and not Role.objects.filter(id=value, brand_id=request.tenant["brand_id"]).exists():
        raise serializers.ValidationError("Role does not belong to your brand.")
    return value


def _validate_outlet(value, request):
    if value is None:
        return value
    if request and hasattr(request, "tenant") and not Outlet.objects.filter(id=value, brand_id=request.tenant["brand_id"]).exists():
        raise serializers.ValidationError("Outlet does not belong to your brand.")
    return value


class EmployeeCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    role_id = serializers.UUIDField()
    outlet_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = Employee
        fields = ["outlet_id", "role_id", "email", "password", "full_name", "is_active"]

    def validate_role_id(self, value):
        return _validate_role(value, self.context.get("request"))

    def validate_outlet_id(self, value):
        return _validate_outlet(value, self.context.get("request"))

    def create(self, validated_data):
        password = validated_data.pop("password")
        employee = Employee(**validated_data)
        employee.set_password(password)
        employee.save()
        return employee


class EmployeeUpdateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8, required=False, allow_blank=False)
    role_id = serializers.UUIDField(required=False)
    outlet_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = Employee
        fields = ["outlet_id", "role_id", "email", "full_name", "is_active", "password"]

    def validate_role_id(self, value):
        return _validate_role(value, self.context.get("request"))

    def validate_outlet_id(self, value):
        return _validate_outlet(value, self.context.get("request"))

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance
